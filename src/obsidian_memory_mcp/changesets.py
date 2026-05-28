"""Grouped proposal workflows above the single-file proposal primitive."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import sqlite3
import uuid
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.proposals._audit import build_event_details
from obsidian_memory_mcp.proposals._db import bootstrap_schema_once
from obsidian_memory_mcp.proposals import (
    ProposalManager,
    ProposalOperation,
    ProposalStatus,
)
from obsidian_memory_mcp.proposals._models import Proposal
from obsidian_memory_mcp.proposals.repository import ProposalRepository
from obsidian_memory_mcp.schema import connect_index_db


class ChangesetStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class FileMutation:
    file_path: str
    operation: ProposalOperation | str
    content: str | None = None


@dataclass(frozen=True)
class Changeset:
    changeset_id: str
    title: str
    description: str | None
    status: ChangesetStatus
    proposal_ids: tuple[str, ...]
    created_at: datetime
    expires_at: datetime
    status_changed_at: datetime | None = None


@dataclass(frozen=True)
class ChangesetCreateResult:
    changeset_id: str
    title: str
    status: ChangesetStatus
    proposal_ids: tuple[str, ...]
    expires_at: datetime

    def as_response(self) -> dict[str, object]:
        return {
            "changeset_id": self.changeset_id,
            "title": self.title,
            "status": self.status.value,
            "proposal_ids": list(self.proposal_ids),
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass(frozen=True)
class ChangesetReviewFile:
    proposal_id: str
    file_path: str
    operation: ProposalOperation
    preview: str | None
    diff: str


@dataclass(frozen=True)
class ChangesetReview:
    changeset_id: str
    title: str
    status: ChangesetStatus
    files: tuple[ChangesetReviewFile, ...]

    @property
    def summary(self) -> str:
        paths = ", ".join(file.file_path for file in self.files)
        return f"{self.title}: {paths}"


@dataclass(frozen=True)
class ChangesetApprovalResult:
    changeset_id: str
    status: ChangesetStatus
    applied_at: datetime
    applied_proposal_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChangesetRejectionResult:
    changeset_id: str
    status: ChangesetStatus
    rejected_at: datetime
    reason: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ChangesetCleanupResult:
    expired_count: int
    removed_changesets: int
    removed_proposals: int
    retention_days: int


@dataclass(frozen=True)
class ChangesetLifecycleEvent:
    event_id: int
    changeset_id: str
    event_type: str
    occurred_at: datetime
    details: dict[str, object]


@dataclass(frozen=True)
class _PreparedProposal:
    proposal: Proposal
    target: Path


class ChangesetManager:
    def __init__(
        self,
        config: ProjectConfig,
        guardrails: GuardrailEvaluator | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        proposal_id_factory: Callable[[], str] | None = None,
    ):
        self._config = config
        self._guardrails = guardrails or GuardrailEvaluator(config)
        self._clock = clock or _utc_now
        self._id_factory = id_factory or _new_changeset_id
        self._proposal_manager = ProposalManager(
            config,
            self._guardrails,
            clock=self._clock,
            id_factory=proposal_id_factory,
        )

    def create(
        self,
        *,
        title: str,
        mutations: Iterable[FileMutation],
        description: str | None = None,
    ) -> ChangesetCreateResult:
        mutation_list = tuple(mutations)
        if len(mutation_list) < 2:
            raise _invalid_request("A changeset requires at least two file mutations.")
        with self._repositories() as (proposal_repository, changesets):
            with proposal_repository.transaction(immediate=True):
                proposal_ids: list[str] = []
                for mutation in mutation_list:
                    created = self._proposal_manager._create_with_repository(
                        proposal_repository,
                        file_path=mutation.file_path,
                        operation=mutation.operation,
                        content=mutation.content,
                    )
                    proposal_ids.append(created.proposal_id)

                proposals = tuple(
                    _fetch_proposal_or_raise(proposal_repository, proposal_id)
                    for proposal_id in proposal_ids
                )
                now = self._now()
                expires_at = min(proposal.expires_at for proposal in proposals)
                changeset = Changeset(
                    changeset_id=self._id_factory(),
                    title=title,
                    description=description,
                    status=ChangesetStatus.PENDING,
                    proposal_ids=tuple(proposal_ids),
                    created_at=now,
                    expires_at=expires_at,
                )
                changesets.insert(changeset)

        return ChangesetCreateResult(
            changeset_id=changeset.changeset_id,
            title=changeset.title,
            status=changeset.status,
            proposal_ids=changeset.proposal_ids,
            expires_at=changeset.expires_at,
        )

    def get(self, changeset_id: str) -> Changeset | None:
        now = self._now()
        with self._repositories() as (proposal_repository, changesets):
            proposal_repository.expire_pending(now)
            changesets.expire_pending(now)
            return changesets.fetch_by_id(changeset_id)

    def proposals(self, changeset_id: str) -> tuple[Proposal, ...]:
        with self._repositories() as (proposal_repository, changesets):
            changeset = _fetch_changeset_or_raise(changesets, changeset_id)
            return _fetch_member_proposals(proposal_repository, changeset)

    def review(self, changeset_id: str) -> ChangesetReview:
        with self._repositories() as (proposal_repository, changesets):
            changeset = _fetch_changeset_or_raise(changesets, changeset_id)
            proposals = _fetch_member_proposals(proposal_repository, changeset)
            files = tuple(_review_file(self._config, proposal) for proposal in proposals)
            return ChangesetReview(
                changeset_id=changeset.changeset_id,
                title=changeset.title,
                status=changeset.status,
                files=files,
            )

    def approve(
        self,
        changeset_id: str,
        *,
        actor: str | None = "operator",
    ) -> ChangesetApprovalResult:
        now = self._now()
        with self._repositories() as (proposal_repository, changesets):
            with proposal_repository.transaction(immediate=True):
                proposal_repository.expire_pending(now)
                changesets.expire_pending(now)
                changeset = _fetch_changeset_or_raise(changesets, changeset_id)
                proposals = _fetch_member_proposals(proposal_repository, changeset)
                changesets.record_event(
                    changeset_id,
                    "changeset_approval_attempt",
                    now,
                    build_event_details({"status": changeset.status.value}, actor=actor),
                )
                self._validate_changeset_pending(changeset, now)
                prepared = tuple(
                    self._prepare_proposal(
                        changeset.changeset_id,
                        proposal_repository,
                        proposal,
                        now,
                    )
                    for proposal in proposals
                )

                snapshots = _snapshot_targets(prepared)
                try:
                    # Keep DB and filesystem transitions aligned:
                    # any failure after a write restores file snapshots and the
                    # surrounding transaction rolls back proposal/changeset status.
                    for item in prepared:
                        _apply_file_change(item.proposal, item.target)
                    for item in prepared:
                        applied = proposal_repository.mark_applied_if_pending(
                            item.proposal.proposal_id,
                            now,
                            actor=actor,
                            workflow_id=changeset.changeset_id,
                        )
                        if not applied:
                            raise _stale_changeset_error(
                                changeset.changeset_id,
                                item.proposal,
                                "Proposal status changed during changeset approval.",
                            )
                    changesets.mark_status_if_pending(
                        changeset.changeset_id,
                        ChangesetStatus.APPLIED,
                        now,
                    )
                    changesets.record_event(
                        changeset.changeset_id,
                        "changeset_applied",
                        now,
                        build_event_details(
                            {"proposal_ids": list(changeset.proposal_ids)},
                            actor=actor,
                        ),
                    )
                except Exception:
                    _restore_snapshots(snapshots)
                    raise

        return ChangesetApprovalResult(
            changeset_id=changeset_id,
            status=ChangesetStatus.APPLIED,
            applied_at=now,
            applied_proposal_ids=changeset.proposal_ids,
        )

    def reject(
        self,
        changeset_id: str,
        *,
        reason: str | None = None,
        notes: str | None = None,
        actor: str | None = "operator",
    ) -> ChangesetRejectionResult:
        now = self._now()
        with self._repositories() as (proposal_repository, changesets):
            with proposal_repository.transaction(immediate=True):
                proposal_repository.expire_pending(now)
                changesets.expire_pending(now)
                changeset = _fetch_changeset_or_raise(changesets, changeset_id)
                self._validate_changeset_pending(changeset, now)
                proposals = _fetch_member_proposals(proposal_repository, changeset)
                for proposal in proposals:
                    if proposal.status is ProposalStatus.PENDING:
                        proposal_repository.mark_rejected_if_pending(
                            proposal.proposal_id,
                            now,
                            reason=reason,
                            notes=notes,
                            actor=actor,
                            workflow_id=changeset.changeset_id,
                        )
                changesets.mark_status_if_pending(
                    changeset.changeset_id,
                    ChangesetStatus.REJECTED,
                    now,
                )
                changesets.record_event(
                    changeset.changeset_id,
                    "changeset_rejected",
                    now,
                    build_event_details(
                        {"proposal_ids": list(changeset.proposal_ids)},
                        reason=reason,
                        notes=notes,
                        actor=actor,
                        workflow_id=changeset.changeset_id,
                    ),
                )

        return ChangesetRejectionResult(
            changeset_id=changeset_id,
            status=ChangesetStatus.REJECTED,
            rejected_at=now,
            reason=reason,
            notes=notes,
        )

    def audit(
        self,
        *,
        changeset_id: str | None = None,
        limit: int = 100,
    ) -> tuple[ChangesetLifecycleEvent, ...]:
        with self._repositories() as (_proposal_repository, changesets):
            return changesets.list_events(changeset_id=changeset_id, limit=limit)

    def cleanup(self, *, retention_days: int | None = None) -> ChangesetCleanupResult:
        resolved_retention_days = retention_days or self._config.proposal_retention_days
        now = self._now()
        with self._repositories() as (proposal_repository, changesets):
            expired_count = changesets.expire_pending(now)
            removed_changesets, removed_proposal_ids = changesets.cleanup_terminal(
                now,
                retention_days=resolved_retention_days,
            )
            removed_proposals = proposal_repository.delete_by_ids(removed_proposal_ids)
        return ChangesetCleanupResult(
            expired_count=expired_count,
            removed_changesets=removed_changesets,
            removed_proposals=removed_proposals,
            retention_days=resolved_retention_days,
        )

    def _prepare_proposal(
        self,
        changeset_id: str,
        repository: ProposalRepository,
        proposal: Proposal,
        now: datetime,
    ) -> _PreparedProposal:
        if proposal.status is not ProposalStatus.PENDING:
            raise _stale_changeset_error(
                changeset_id,
                proposal,
                f"Proposal is {proposal.status.value}.",
            )
        if now >= proposal.expires_at:
            repository.mark_expired(proposal.proposal_id, now, reason="ttl_elapsed")
            raise _stale_changeset_error(changeset_id, proposal, "Proposal expired.")

        target = self._guardrails.check_write(proposal.file_path)
        current_hash = _file_hash_or_none(target)
        rejection = _stale_rejection_message(proposal, current_hash)
        if rejection is not None:
            repository.record_event(
                proposal.proposal_id,
                "apply_rejection",
                now,
                build_event_details(
                    {"reason": "file_state_conflict"},
                    workflow_id=changeset_id,
                ),
            )
            raise _stale_changeset_error(changeset_id, proposal, rejection)
        return _PreparedProposal(proposal=proposal, target=target)

    def _validate_changeset_pending(
        self,
        changeset: Changeset,
        now: datetime,
    ) -> None:
        if changeset.status is not ChangesetStatus.PENDING:
            raise _invalid_request(
                f"Changeset '{changeset.changeset_id}' is "
                f"{changeset.status.value} and cannot be approved."
            )
        if now >= changeset.expires_at:
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_STALE_PROPOSAL,
                    message=(
                        f"Changeset '{changeset.changeset_id}' has expired."
                    ),
                    details={
                        "changeset_id": changeset.changeset_id,
                        "conflict_type": "file_state",
                    },
                )
            )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)

    @contextmanager
    def _repositories(self) -> Iterator[tuple[ProposalRepository, "_ChangesetRepository"]]:
        database_existed = self._config.index_db_location.exists()
        connection = connect_index_db(self._config.index_db_location)
        proposal_repository = ProposalRepository(connection)
        try:
            bootstrap_schema_once(
                connection,
                self._config.index_db_location,
                database_existed=database_existed,
            )
            yield proposal_repository, _ChangesetRepository(connection)
        finally:
            proposal_repository.close()
            connection.close()


class _ChangesetRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def insert(self, changeset: Changeset) -> None:
        with self._transaction(immediate=True):
            self._connection.execute(
                """
                INSERT INTO proposal_changesets (
                    id, title, description, status, created_at, expires_at,
                    status_changed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    changeset.changeset_id,
                    changeset.title,
                    changeset.description,
                    changeset.status.value,
                    _to_iso(changeset.created_at),
                    _to_iso(changeset.expires_at),
                    _optional_iso(changeset.status_changed_at),
                ),
            )
            for ordinal, proposal_id in enumerate(changeset.proposal_ids):
                self._connection.execute(
                    """
                    INSERT INTO proposal_changeset_members (
                        changeset_id, proposal_id, ordinal, role
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (changeset.changeset_id, proposal_id, ordinal, "member"),
                )
            self._insert_event(
                changeset.changeset_id,
                "changeset_created",
                changeset.created_at,
                {
                    "title": changeset.title,
                    "proposal_ids": list(changeset.proposal_ids),
                    "status": changeset.status.value,
                },
            )

    def fetch_by_id(self, changeset_id: str) -> Changeset | None:
        row = self._connection.execute(
            "SELECT * FROM proposal_changesets WHERE id = ?",
            (changeset_id,),
        ).fetchone()
        if row is None:
            return None
        return _changeset_from_row(row, self._member_ids(changeset_id))

    def expire_pending(self, now: datetime) -> int:
        rows = self._connection.execute(
            """
            SELECT id
            FROM proposal_changesets
            WHERE status = ? AND expires_at <= ?
            ORDER BY created_at
            """,
            (ChangesetStatus.PENDING.value, _to_iso(now)),
        ).fetchall()
        if not rows:
            return 0

        with self._transaction(immediate=True):
            for row in rows:
                changeset_id = row["id"]
                self._connection.execute(
                    """
                    UPDATE proposal_changesets
                    SET status = ?, status_changed_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (
                        ChangesetStatus.EXPIRED.value,
                        _to_iso(now),
                        changeset_id,
                        ChangesetStatus.PENDING.value,
                    ),
                )
                self._insert_event(
                    changeset_id,
                    "changeset_expired",
                    now,
                    {"reason": "ttl_elapsed"},
                )
        return len(rows)

    def mark_status_if_pending(
        self,
        changeset_id: str,
        status: ChangesetStatus,
        now: datetime,
    ) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE proposal_changesets
            SET status = ?, status_changed_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                status.value,
                _to_iso(now),
                changeset_id,
                ChangesetStatus.PENDING.value,
            ),
        )
        return cursor.rowcount == 1

    def record_event(
        self,
        changeset_id: str,
        event_type: str,
        now: datetime,
        details: dict[str, object],
    ) -> None:
        self._insert_event(changeset_id, event_type, now, details)

    def list_events(
        self,
        *,
        changeset_id: str | None = None,
        limit: int = 100,
    ) -> tuple[ChangesetLifecycleEvent, ...]:
        if limit < 1:
            raise ValueError("Event list limit must be positive.")
        conditions: list[str] = []
        parameters: list[object] = []
        if changeset_id is not None:
            conditions.append("changeset_id = ?")
            parameters.append(changeset_id)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT id, changeset_id, event_type, occurred_at, details
            FROM proposal_changeset_events
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(_changeset_event_from_row(row) for row in rows)

    def cleanup_terminal(
        self,
        now: datetime,
        *,
        retention_days: int,
    ) -> tuple[int, tuple[str, ...]]:
        cutoff = _to_iso(now - timedelta(days=retention_days))
        rows = self._connection.execute(
            """
            SELECT id
            FROM proposal_changesets
            WHERE status IN (?, ?, ?)
              AND COALESCE(status_changed_at, created_at) <= ?
            """,
            (
                ChangesetStatus.APPLIED.value,
                ChangesetStatus.REJECTED.value,
                ChangesetStatus.EXPIRED.value,
                cutoff,
            ),
        ).fetchall()
        if not rows:
            return 0, ()

        removed_proposal_ids: list[str] = []
        with self._transaction(immediate=True):
            for row in rows:
                changeset_id = row["id"]
                proposal_ids = self._member_ids(changeset_id)
                self._connection.execute(
                    "DELETE FROM proposal_changesets WHERE id = ?",
                    (changeset_id,),
                )
                removed_proposal_ids.extend(proposal_ids)
        deduped_ids = tuple(dict.fromkeys(removed_proposal_ids))
        return len(rows), deduped_ids

    @contextmanager
    def _transaction(self, *, immediate: bool = False) -> Iterator[None]:
        if self._connection.in_transaction:
            yield
            return
        if immediate:
            self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def _member_ids(self, changeset_id: str) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT proposal_id
            FROM proposal_changeset_members
            WHERE changeset_id = ?
            ORDER BY ordinal
            """,
            (changeset_id,),
        ).fetchall()
        return tuple(row["proposal_id"] for row in rows)

    def _insert_event(
        self,
        changeset_id: str,
        event_type: str,
        occurred_at: datetime,
        details: dict[str, object],
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO proposal_changeset_events (
                changeset_id, event_type, occurred_at, details
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                changeset_id,
                event_type,
                _to_iso(occurred_at),
                json.dumps(details, sort_keys=True, separators=(",", ":")),
            ),
        )


def _review_file(config: ProjectConfig, proposal: Proposal) -> ChangesetReviewFile:
    return ChangesetReviewFile(
        proposal_id=proposal.proposal_id,
        file_path=proposal.file_path,
        operation=proposal.operation,
        preview=_preview(proposal),
        diff=proposal_diff(config, proposal),
    )


def proposal_diff(config: ProjectConfig, proposal: Proposal) -> str:
    target = config.vault_path / proposal.file_path
    current = "" if proposal.operation is ProposalOperation.CREATE else _read_text(target)
    proposed = "" if proposal.operation is ProposalOperation.DELETE else proposal.content
    proposed = proposed or ""
    lines = difflib.unified_diff(
        current.splitlines(),
        proposed.splitlines(),
        fromfile=f"a/{proposal.file_path}",
        tofile=f"b/{proposal.file_path}",
        lineterm="",
    )
    return "\n".join(lines)


def _fetch_changeset_or_raise(
    repository: _ChangesetRepository,
    changeset_id: str,
) -> Changeset:
    changeset = repository.fetch_by_id(changeset_id)
    if changeset is None:
        raise _invalid_request(f"Changeset '{changeset_id}' does not exist.")
    return changeset


def _fetch_member_proposals(
    repository: ProposalRepository,
    changeset: Changeset,
) -> tuple[Proposal, ...]:
    return tuple(
        _fetch_proposal_or_raise(repository, proposal_id)
        for proposal_id in changeset.proposal_ids
    )


def _fetch_proposal_or_raise(
    repository: ProposalRepository,
    proposal_id: str,
) -> Proposal:
    proposal = repository.fetch_by_id(proposal_id)
    if proposal is None:
        raise _invalid_request(f"Proposal '{proposal_id}' does not exist.")
    return proposal


def _snapshot_targets(
    prepared: tuple[_PreparedProposal, ...],
) -> tuple[tuple[Path, bytes | None], ...]:
    return tuple(
        (item.target, item.target.read_bytes() if item.target.exists() else None)
        for item in prepared
    )


def _restore_snapshots(snapshots: tuple[tuple[Path, bytes | None], ...]) -> None:
    for path, content in reversed(snapshots):
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, content)


def _apply_file_change(proposal: Proposal, target: Path) -> int:
    if proposal.operation is ProposalOperation.DELETE:
        target.unlink()
        return 0
    if proposal.content is None:
        raise RuntimeError(f"Proposal '{proposal.proposal_id}' has no content.")
    content_bytes = proposal.content.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, content_bytes)
    return len(content_bytes)


def _atomic_write(target: Path, content: bytes) -> None:
    temporary_path = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_bytes(content)
        os.replace(temporary_path, target)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


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


def _file_hash_or_none(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preview(proposal: Proposal) -> str | None:
    if proposal.operation is ProposalOperation.DELETE or proposal.content is None:
        return None
    return proposal.content[:500]


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _changeset_from_row(
    row: sqlite3.Row,
    proposal_ids: tuple[str, ...],
) -> Changeset:
    return Changeset(
        changeset_id=row["id"],
        title=row["title"],
        description=row["description"],
        status=ChangesetStatus(row["status"]),
        proposal_ids=proposal_ids,
        created_at=_from_iso(row["created_at"]),
        expires_at=_from_iso(row["expires_at"]),
        status_changed_at=_optional_from_iso(row["status_changed_at"]),
    )


def _changeset_event_from_row(row: sqlite3.Row) -> ChangesetLifecycleEvent:
    return ChangesetLifecycleEvent(
        event_id=int(row["id"]),
        changeset_id=row["changeset_id"],
        event_type=row["event_type"],
        occurred_at=_from_iso(row["occurred_at"]),
        details=json.loads(row["details"]),
    )


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _optional_iso(value: datetime | None) -> str | None:
    return _to_iso(value) if value is not None else None


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_from_iso(value: str | None) -> datetime | None:
    return _from_iso(value) if value is not None else None


def _new_changeset_id() -> str:
    return f"changeset-{uuid.uuid4()}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _invalid_request(message: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(ErrorCode.ERR_INVALID_REQUEST, message=message)
    )


def _stale_changeset_error(
    changeset_id: str,
    proposal: Proposal,
    reason: str,
) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(
            ErrorCode.ERR_STALE_PROPOSAL,
            message=(
                f"Changeset '{changeset_id}' has a file-state conflict for "
                f"proposal '{proposal.proposal_id}': {reason}"
            ),
            details={
                "changeset_id": changeset_id,
                "proposal_id": proposal.proposal_id,
                "file_path": proposal.file_path,
                "conflict_type": "file_state",
                "suggestion": "Create a fresh changeset against the current file state.",
            },
        )
    )
