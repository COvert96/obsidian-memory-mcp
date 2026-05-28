"""SQLAlchemy Core persistence for proposal metadata and lifecycle records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.pool import StaticPool

from obsidian_memory_mcp.database._tables import (
    proposal_changeset_members,
    proposal_events,
    proposals,
)
from obsidian_memory_mcp.proposals._audit import build_event_details
from obsidian_memory_mcp.proposals._models import (
    Proposal,
    ProposalLifecycleEvent,
    ProposalOperation,
    ProposalStatus,
)


class ProposalRepository:
    def __init__(self, connection: Connection | sqlite3.Connection):
        self._raw_connection: sqlite3.Connection | None = None
        self._engine = None
        self._owns_connection = False
        if isinstance(connection, Connection):
            self._connection = connection
        else:
            self._raw_connection = connection
            proxy = _NonClosingSQLiteConnection(connection)
            self._engine = create_engine(
                "sqlite+pysqlite://",
                creator=lambda: proxy,
                poolclass=StaticPool,
                pool_reset_on_return=None,
            )
            self._connection = self._engine.connect()
            self._owns_connection = True

    def close(self) -> None:
        if not self._owns_connection:
            return
        self._connection.close()
        if self._engine is not None:
            self._engine.dispose()
        self._owns_connection = False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            return None

    @contextmanager
    def transaction(
        self,
        *,
        immediate: bool = False,
        commit_on: tuple[type[BaseException], ...] = (),
    ) -> Iterator[None]:
        if self._raw_connection is not None:
            with self._sqlite_transaction(immediate=immediate, commit_on=commit_on):
                yield
            return

        if self._connection.in_transaction():
            yield
            return

        if immediate:
            self._connection.exec_driver_sql("BEGIN IMMEDIATE")

        try:
            yield
        except Exception as error:
            if commit_on and isinstance(error, commit_on):
                self._connection.commit()
            else:
                self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def insert(self, proposal: Proposal) -> None:
        with self.transaction():
            self._connection.execute(
                insert(proposals).values(
                    id=proposal.proposal_id,
                    file_path=proposal.file_path,
                    operation=proposal.operation.value,
                    content=proposal.content,
                    old_hash=proposal.old_hash,
                    new_hash=proposal.new_hash,
                    status=proposal.status.value,
                    created_at=_to_iso(proposal.created_at),
                    expires_at=_to_iso(proposal.expires_at),
                    status_changed_at=_optional_iso(proposal.status_changed_at),
                    applied_at=_optional_iso(proposal.applied_at),
                )
            )
            self._insert_event(
                proposal.proposal_id,
                "created",
                proposal.created_at,
                {
                    "file_path": proposal.file_path,
                    "operation": proposal.operation.value,
                    "status": proposal.status.value,
                },
            )

    def fetch_by_id(self, proposal_id: str) -> Proposal | None:
        row = (
            self._connection.execute(
                select(proposals).where(proposals.c.id == proposal_id)
            )
            .mappings()
            .first()
        )
        return _proposal_from_row(row) if row is not None else None

    def list(
        self,
        *,
        status: ProposalStatus | None = None,
        file_path: str | None = None,
        created_after: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Proposal, ...]:
        statement = select(proposals)
        if status is not None:
            statement = statement.where(proposals.c.status == status.value)
        if file_path is not None:
            statement = statement.where(proposals.c.file_path == file_path)
        if created_after is not None:
            statement = statement.where(proposals.c.created_at >= _to_iso(created_after))
        statement = statement.order_by(proposals.c.created_at.desc(), proposals.c.id.desc())
        statement = statement.limit(limit)
        rows = self._connection.execute(statement).mappings().all()
        return tuple(_proposal_from_row(row) for row in rows)

    def expire_pending(self, now: datetime) -> int:
        expired_rows = (
            self._connection.execute(
                select(proposals.c.id)
                .where(
                    proposals.c.status == ProposalStatus.PENDING.value,
                    proposals.c.expires_at <= _to_iso(now),
                )
                .order_by(proposals.c.created_at)
            )
            .mappings()
            .all()
        )
        if not expired_rows:
            return 0

        with self.transaction():
            for row in expired_rows:
                proposal_id = str(row["id"])
                self._connection.execute(
                    update(proposals)
                    .where(
                        proposals.c.id == proposal_id,
                        proposals.c.status == ProposalStatus.PENDING.value,
                    )
                    .values(
                        status=ProposalStatus.EXPIRED.value,
                        status_changed_at=_to_iso(now),
                    )
                )
                self._insert_event(
                    proposal_id,
                    "expired",
                    now,
                    {"reason": "ttl_elapsed"},
                )
        return len(expired_rows)

    def mark_applied_if_pending(
        self,
        proposal_id: str,
        now: datetime,
        *,
        actor: str | None = None,
        workflow_id: str | None = None,
    ) -> bool:
        with self.transaction():
            result = self._connection.execute(
                update(proposals)
                .where(
                    proposals.c.id == proposal_id,
                    proposals.c.status == ProposalStatus.PENDING.value,
                )
                .values(
                    status=ProposalStatus.APPLIED.value,
                    status_changed_at=_to_iso(now),
                    applied_at=_to_iso(now),
                )
            )
            if result.rowcount != 1:
                return False
            details = build_event_details(
                {"status": "applied"},
                actor=actor,
                workflow_id=workflow_id,
            )
            self._insert_event(proposal_id, "applied", now, details)
        return True

    def mark_rejected_if_pending(
        self,
        proposal_id: str,
        now: datetime,
        *,
        reason: str | None = None,
        notes: str | None = None,
        actor: str | None = None,
        workflow_id: str | None = None,
    ) -> bool:
        with self.transaction():
            result = self._connection.execute(
                update(proposals)
                .where(
                    proposals.c.id == proposal_id,
                    proposals.c.status == ProposalStatus.PENDING.value,
                )
                .values(
                    status=ProposalStatus.REJECTED.value,
                    status_changed_at=_to_iso(now),
                )
            )
            if result.rowcount != 1:
                return False
            details = build_event_details(
                {"status": "rejected"},
                reason=reason,
                notes=notes,
                actor=actor,
                workflow_id=workflow_id,
            )
            self._insert_event(proposal_id, "rejected", now, details)
        return True

    def mark_expired(self, proposal_id: str, now: datetime, *, reason: str) -> bool:
        with self.transaction():
            result = self._connection.execute(
                update(proposals)
                .where(
                    proposals.c.id == proposal_id,
                    proposals.c.status == ProposalStatus.PENDING.value,
                )
                .values(
                    status=ProposalStatus.EXPIRED.value,
                    status_changed_at=_to_iso(now),
                )
            )
            if result.rowcount != 1:
                return False
            self._insert_event(proposal_id, "expired", now, {"reason": reason})
        return True

    def record_event(
        self,
        proposal_id: str,
        event_type: str,
        now: datetime,
        details: dict[str, Any],
    ) -> None:
        with self.transaction():
            self._insert_event(proposal_id, event_type, now, details)

    def events(self, proposal_id: str) -> tuple[ProposalLifecycleEvent, ...]:
        rows = (
            self._connection.execute(
                select(
                    proposal_events.c.id,
                    proposal_events.c.proposal_id,
                    proposal_events.c.event_type,
                    proposal_events.c.occurred_at,
                    proposal_events.c.details,
                )
                .where(proposal_events.c.proposal_id == proposal_id)
                .order_by(proposal_events.c.id)
            )
            .mappings()
            .all()
        )
        return tuple(_event_from_row(row) for row in rows)

    def list_events(
        self,
        *,
        proposal_id: str | None = None,
        limit: int = 100,
    ) -> tuple[ProposalLifecycleEvent, ...]:
        if limit < 1:
            raise ValueError("Event list limit must be positive.")
        statement = select(
            proposal_events.c.id,
            proposal_events.c.proposal_id,
            proposal_events.c.event_type,
            proposal_events.c.occurred_at,
            proposal_events.c.details,
        )
        if proposal_id is not None:
            statement = statement.where(proposal_events.c.proposal_id == proposal_id)
        statement = statement.order_by(proposal_events.c.id.desc()).limit(limit)
        rows = self._connection.execute(statement).mappings().all()
        return tuple(_event_from_row(row) for row in rows)

    def cleanup_terminal(
        self,
        now: datetime,
        *,
        retention_days: int,
    ) -> int:
        cutoff = _to_iso(now - timedelta(days=retention_days))
        member_exists = exists(
            select(1).where(proposal_changeset_members.c.proposal_id == proposals.c.id)
        )
        with self.transaction():
            result = self._connection.execute(
                delete(proposals).where(
                    proposals.c.status.in_(
                        (
                            ProposalStatus.APPLIED.value,
                            ProposalStatus.REJECTED.value,
                            ProposalStatus.EXPIRED.value,
                        )
                    ),
                    func.coalesce(
                        proposals.c.status_changed_at,
                        proposals.c.applied_at,
                        proposals.c.created_at,
                    )
                    <= cutoff,
                    ~member_exists,
                )
            )
        return int(result.rowcount)

    def delete_by_ids(self, proposal_ids: tuple[str, ...]) -> int:
        if not proposal_ids:
            return 0
        with self.transaction():
            result = self._connection.execute(
                delete(proposals).where(proposals.c.id.in_(proposal_ids))
            )
        return int(result.rowcount)

    def _insert_event(
        self,
        proposal_id: str,
        event_type: str,
        occurred_at: datetime,
        details: dict[str, Any],
    ) -> None:
        self._connection.execute(
            insert(proposal_events).values(
                proposal_id=proposal_id,
                event_type=event_type,
                occurred_at=_to_iso(occurred_at),
                details=json.dumps(details, sort_keys=True, separators=(",", ":")),
            )
        )

    @contextmanager
    def _sqlite_transaction(
        self,
        *,
        immediate: bool,
        commit_on: tuple[type[BaseException], ...],
    ) -> Iterator[None]:
        raw_connection = self._raw_connection
        if raw_connection is None:
            raise RuntimeError("Missing sqlite3 connection for sqlite transaction.")
        if raw_connection.in_transaction:
            yield
            return

        if immediate:
            raw_connection.execute("BEGIN IMMEDIATE")

        try:
            yield
        except Exception as error:
            if commit_on and isinstance(error, commit_on):
                raw_connection.commit()
            else:
                raw_connection.rollback()
            raise
        else:
            raw_connection.commit()


class _NonClosingSQLiteConnection:
    def __init__(self, wrapped: sqlite3.Connection):
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def close(self) -> None:
        return None


def _proposal_from_row(row: Any) -> Proposal:
    return Proposal(
        proposal_id=str(row["id"]),
        file_path=str(row["file_path"]),
        operation=ProposalOperation(str(row["operation"])),
        content=str(row["content"]) if row["content"] is not None else None,
        old_hash=str(row["old_hash"]) if row["old_hash"] is not None else None,
        new_hash=str(row["new_hash"]) if row["new_hash"] is not None else None,
        status=ProposalStatus(str(row["status"])),
        created_at=_from_iso(str(row["created_at"])),
        expires_at=_from_iso(str(row["expires_at"])),
        status_changed_at=_optional_from_iso(row["status_changed_at"]),
        applied_at=_optional_from_iso(row["applied_at"]),
    )


def _event_from_row(row: Any) -> ProposalLifecycleEvent:
    return ProposalLifecycleEvent(
        event_id=int(row["id"]),
        proposal_id=str(row["proposal_id"]),
        event_type=str(row["event_type"]),
        occurred_at=_from_iso(str(row["occurred_at"])),
        details=json.loads(str(row["details"])),
    )


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _optional_iso(value: datetime | None) -> str | None:
    return _to_iso(value) if value is not None else None


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_from_iso(value: object) -> datetime | None:
    return _from_iso(str(value)) if value is not None else None
