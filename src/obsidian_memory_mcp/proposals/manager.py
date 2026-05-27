"""Proposal workflow orchestration and guarded file application."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Iterator

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.proposals._models import (
    Proposal,
    ProposalApprovalResult,
    ProposalCreateResult,
    ProposalLifecycleEvent,
    ProposalListItem,
    ProposalOperation,
    ProposalRejectionResult,
    ProposalStatus,
)
from obsidian_memory_mcp.proposals.repository import ProposalRepository
from obsidian_memory_mcp.schema import bootstrap_schema, connect_index_db
from obsidian_memory_mcp.wikilinks import escape_wikilink_alias_separator

PREVIEW_MAX_CHARS = 500
PREVIEW_ELLIPSIS = "..."
_BOOTSTRAPPED_SCHEMA_PATHS: set[Path] = set()
_SCHEMA_BOOTSTRAP_LOCK = Lock()


class ProposalManager:
    def __init__(
        self,
        config: ProjectConfig,
        guardrails: GuardrailEvaluator | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self._config = config
        self._guardrails = guardrails or GuardrailEvaluator(config)
        self._clock = clock or _utc_now
        self._id_factory = id_factory or _new_proposal_id

    def create(
        self,
        *,
        file_path: str,
        operation: ProposalOperation | str,
        content: str | None = None,
    ) -> ProposalCreateResult:
        normalized_operation = _normalize_operation(operation)
        normalized_content = _normalize_content_for_write(
            normalized_operation,
            content,
        )
        _validate_content(
            normalized_operation,
            normalized_content,
            max_content_bytes=self._config.max_proposal_content_bytes,
        )
        target = self._guardrails.check_write(file_path)
        normalized_file_path = self._relative_path(target)
        old_hash = self._old_hash_for(
            normalized_operation, target, normalized_file_path
        )
        new_hash = (
            _content_hash(normalized_content) if normalized_content is not None else None
        )
        ttl_seconds = self._ttl_seconds()
        created_at = self._now()
        proposal = Proposal(
            proposal_id=self._id_factory(),
            file_path=normalized_file_path,
            operation=normalized_operation,
            content=normalized_content,
            old_hash=old_hash,
            new_hash=new_hash,
            status=ProposalStatus.PENDING,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
        )

        with self._repository() as repository:
            repository.insert(proposal)

        return ProposalCreateResult(
            proposal_id=proposal.proposal_id,
            file_path=proposal.file_path,
            operation=proposal.operation,
            old_hash=proposal.old_hash,
            new_hash=proposal.new_hash,
            ttl_seconds=ttl_seconds,
        )

    def get(self, proposal_id: str) -> Proposal | None:
        with self._repository() as repository:
            repository.expire_pending(self._now())
            return repository.fetch_by_id(proposal_id)

    def list(
        self,
        *,
        status: ProposalStatus | str | None = None,
        file_path: str | None = None,
        created_after: datetime | None = None,
        limit: int = 50,
    ) -> tuple[ProposalListItem, ...]:
        if limit < 1:
            raise _invalid_request("Proposal list limit must be a positive integer.")

        normalized_status = _normalize_status(status) if status is not None else None
        normalized_file_path = (
            self._relative_path(self._guardrails.check_write(file_path))
            if file_path is not None
            else None
        )
        with self._repository() as repository:
            repository.expire_pending(self._now())
            proposals = repository.list(
                status=normalized_status,
                file_path=normalized_file_path,
                created_after=created_after,
                limit=limit,
            )
        return tuple(_list_item(proposal) for proposal in proposals)

    def approve(self, proposal_id: str) -> ProposalApprovalResult:
        now = self._now()
        with self._repository() as repository:
            with repository.transaction(
                immediate=True,
                commit_on=(ToolExecutionError,),
            ):
                proposal = _fetch_proposal_or_raise(repository, proposal_id)
                repository.record_event(
                    proposal.proposal_id,
                    "approval_attempt",
                    now,
                    {"status": proposal.status.value},
                )
                if proposal.status is not ProposalStatus.PENDING:
                    self._record_apply_rejection(
                        repository,
                        proposal,
                        now,
                        reason=f"status_{proposal.status.value}",
                    )
                    if proposal.status is ProposalStatus.EXPIRED:
                        raise _stale_error(proposal, "Proposal has expired.")
                    raise _invalid_request(
                        f"Proposal '{proposal.proposal_id}' is {proposal.status.value} "
                        "and cannot be approved."
                    )
                if now >= proposal.expires_at:
                    repository.mark_expired(
                        proposal.proposal_id,
                        now,
                        reason="ttl_elapsed",
                    )
                    self._record_apply_rejection(
                        repository,
                        proposal,
                        now,
                        reason="expired",
                    )
                    raise _stale_error(proposal, "Proposal has expired.")

                try:
                    target = self._guardrails.check_write(proposal.file_path)
                except ToolExecutionError:
                    self._record_apply_rejection(
                        repository,
                        proposal,
                        now,
                        reason="guardrail_violation",
                    )
                    raise

                current_hash = _file_hash_or_none(target)
                rejection_message = _stale_rejection_message(proposal, current_hash)
                if rejection_message is not None:
                    self._record_apply_rejection(
                        repository,
                        proposal,
                        now,
                        reason="hash_mismatch",
                    )
                    raise _stale_error(proposal, rejection_message)

                try:
                    file_size_bytes = _apply_file_change(proposal, target)
                except FileNotFoundError:
                    self._record_apply_rejection(
                        repository,
                        proposal,
                        now,
                        reason="target_missing",
                    )
                    raise _stale_error(
                        proposal,
                        f"Target file '{proposal.file_path}' no longer exists.",
                    ) from None

                if not repository.mark_applied_if_pending(proposal.proposal_id, now):
                    self._record_apply_rejection(
                        repository,
                        proposal,
                        now,
                        reason="status_changed",
                    )
                    raise _stale_error(
                        proposal,
                        "Proposal status changed during approval.",
                    )

        return ProposalApprovalResult(
            proposal_id=proposal.proposal_id,
            file_path=proposal.file_path,
            operation=proposal.operation,
            status=ProposalStatus.APPLIED,
            written_at=now,
            file_size_bytes=file_size_bytes,
        )

    def reject(self, proposal_id: str) -> ProposalRejectionResult:
        now = self._now()
        with self._repository() as repository:
            with repository.transaction(
                immediate=True,
                commit_on=(ToolExecutionError,),
            ):
                proposal = _fetch_proposal_or_raise(repository, proposal_id)
                if proposal.status is not ProposalStatus.PENDING:
                    if proposal.status is ProposalStatus.EXPIRED:
                        raise _stale_error(proposal, "Proposal has expired.")
                    raise _invalid_request(
                        f"Proposal '{proposal.proposal_id}' is {proposal.status.value} "
                        "and cannot be rejected."
                    )
                if now >= proposal.expires_at:
                    repository.mark_expired(
                        proposal.proposal_id,
                        now,
                        reason="ttl_elapsed",
                    )
                    raise _stale_error(proposal, "Proposal has expired.")
                if not repository.mark_rejected_if_pending(proposal.proposal_id, now):
                    raise _stale_error(
                        proposal,
                        "Proposal status changed during rejection.",
                    )

        return ProposalRejectionResult(
            proposal_id=proposal.proposal_id,
            file_path=proposal.file_path,
            operation=proposal.operation,
            status=ProposalStatus.REJECTED,
            rejected_at=now,
        )

    def events(self, proposal_id: str) -> tuple[ProposalLifecycleEvent, ...]:
        with self._repository() as repository:
            return repository.events(proposal_id)

    def _old_hash_for(
        self,
        operation: ProposalOperation,
        target: Path,
        file_path: str,
    ) -> str | None:
        if operation is ProposalOperation.CREATE:
            if target.exists():
                raise _invalid_request(
                    f"Create proposal target '{file_path}' already exists."
                )
            return None

        if not target.is_file():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_MISSING_FILE,
                    details={"file_path": file_path},
                )
            )
        return _sha256(target.read_bytes())

    def _relative_path(self, target: Path) -> str:
        return target.relative_to(self._config.vault_path).as_posix()

    def _ttl_seconds(self) -> int:
        max_seconds = self._config.max_proposal_ttl_hours * 3600
        return min(self._config.proposal_ttl_seconds, max_seconds)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)

    def _record_apply_rejection(
        self,
        repository: ProposalRepository,
        proposal: Proposal,
        now: datetime,
        *,
        reason: str,
    ) -> None:
        repository.record_event(
            proposal.proposal_id,
            "apply_rejection",
            now,
            {"reason": reason, "status": proposal.status.value},
        )

    @contextmanager
    def _repository(self) -> Iterator[ProposalRepository]:
        database_existed = self._config.index_db_location.exists()
        connection = connect_index_db(self._config.index_db_location)
        try:
            _bootstrap_schema_once(
                connection,
                self._config.index_db_location,
                database_existed=database_existed,
            )
            yield ProposalRepository(connection)
        finally:
            connection.close()


def _list_item(proposal: Proposal) -> ProposalListItem:
    return ProposalListItem(
        proposal_id=proposal.proposal_id,
        file_path=proposal.file_path,
        operation=proposal.operation,
        status=proposal.status,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        old_hash=proposal.old_hash,
        new_hash=proposal.new_hash,
        preview=_preview(proposal),
    )


def _preview(proposal: Proposal) -> str | None:
    if proposal.operation is ProposalOperation.DELETE or proposal.content is None:
        return None
    if len(proposal.content) <= PREVIEW_MAX_CHARS:
        return proposal.content
    return _truncate_at_word_boundary(proposal.content, PREVIEW_MAX_CHARS)


def _normalize_operation(operation: ProposalOperation | str) -> ProposalOperation:
    try:
        return ProposalOperation(operation)
    except ValueError as error:
        allowed = ", ".join(item.value for item in ProposalOperation)
        raise _invalid_request(
            f"Proposal operation must be one of: {allowed}."
        ) from error


def _normalize_status(status: ProposalStatus | str) -> ProposalStatus:
    try:
        return ProposalStatus(status)
    except ValueError as error:
        allowed = ", ".join(item.value for item in ProposalStatus)
        raise _invalid_request(f"Proposal status must be one of: {allowed}.") from error


def _validate_content(
    operation: ProposalOperation,
    content: str | None,
    *,
    max_content_bytes: int,
) -> None:
    if operation in {ProposalOperation.CREATE, ProposalOperation.UPDATE}:
        if content is None:
            raise _invalid_request(
                f"Content is required for {operation.value} proposals."
            )
        content_size = len(content.encode("utf-8"))
        if content_size > max_content_bytes:
            raise _invalid_request(
                f"Proposal content is {content_size} bytes, which exceeds "
                f"the configured limit of {max_content_bytes} bytes."
            )
        return

    if content is not None:
        raise _invalid_request("Delete proposals must omit content.")


def _truncate_at_word_boundary(content: str, max_chars: int) -> str:
    window = content[: max_chars - len(PREVIEW_ELLIPSIS)]
    boundary = max(window.rfind(" "), window.rfind("\n"), window.rfind("\t"))
    if boundary > max_chars // 2:
        return f"{window[:boundary].rstrip()}{PREVIEW_ELLIPSIS}"
    return f"{window.rstrip()}{PREVIEW_ELLIPSIS}"


def _fetch_proposal_or_raise(
    repository: ProposalRepository,
    proposal_id: str,
) -> Proposal:
    proposal = repository.fetch_by_id(proposal_id)
    if proposal is None:
        raise _invalid_request(f"Proposal '{proposal_id}' does not exist.")
    return proposal


def _stale_rejection_message(
    proposal: Proposal,
    current_hash: str | None,
) -> str | None:
    if proposal.operation is ProposalOperation.CREATE:
        if current_hash is not None:
            return f"Target file '{proposal.file_path}' already exists."
        return None

    if current_hash == proposal.old_hash:
        return None

    if proposal.operation is ProposalOperation.DELETE and current_hash is None:
        return f"Target file '{proposal.file_path}' no longer exists."

    return f"Target file '{proposal.file_path}' changed since proposal creation."


def _apply_file_change(proposal: Proposal, target: Path) -> int:
    if proposal.operation is ProposalOperation.DELETE:
        target.unlink()
        return 0

    if proposal.content is None:
        raise RuntimeError(f"Proposal '{proposal.proposal_id}' has no content.")

    content_bytes = proposal.content.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_bytes(content_bytes)
        os.replace(temporary_path, target)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return len(content_bytes)


def _file_hash_or_none(path: Path) -> str | None:
    if not path.is_file():
        return None
    return _sha256(path.read_bytes())


def _content_hash(content: str) -> str:
    return _sha256(content.encode("utf-8"))


def _normalize_content_for_write(
    operation: ProposalOperation,
    content: str | None,
) -> str | None:
    if content is None:
        return None
    if operation in {ProposalOperation.CREATE, ProposalOperation.UPDATE}:
        return escape_wikilink_alias_separator(content)
    return content


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _new_proposal_id() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _bootstrap_schema_once(
    connection: sqlite3.Connection,
    index_db_path: Path,
    *,
    database_existed: bool,
) -> None:
    if index_db_path.name == ":memory:":
        bootstrap_schema(connection)
        return

    cache_key = index_db_path.resolve(strict=False)
    with _SCHEMA_BOOTSTRAP_LOCK:
        if database_existed and cache_key in _BOOTSTRAPPED_SCHEMA_PATHS:
            return
        bootstrap_schema(connection)
        _BOOTSTRAPPED_SCHEMA_PATHS.add(cache_key)


def _invalid_request(message: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(ErrorCode.ERR_INVALID_REQUEST, message=message)
    )


def _stale_error(proposal: Proposal, reason: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(
            ErrorCode.ERR_STALE_PROPOSAL,
            message=f"Proposal '{proposal.proposal_id}' is stale: {reason}",
            details={
                "proposal_id": proposal.proposal_id,
                "file_path": proposal.file_path,
                "status": proposal.status.value,
                "suggestion": "Create a fresh proposal against the current file state.",
            },
        )
    )
