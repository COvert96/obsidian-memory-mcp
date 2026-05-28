"""SQLite persistence for proposal metadata and lifecycle records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from obsidian_memory_mcp.proposals._audit import build_event_details
from obsidian_memory_mcp.proposals._models import (
    Proposal,
    ProposalLifecycleEvent,
    ProposalOperation,
    ProposalStatus,
)


class ProposalRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    @contextmanager
    def transaction(
        self,
        *,
        immediate: bool = False,
        commit_on: tuple[type[BaseException], ...] = (),
    ) -> Iterator[None]:
        if self._connection.in_transaction:
            yield
            return

        if immediate:
            self._connection.execute("BEGIN IMMEDIATE")

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
                """
                INSERT INTO proposals (
                    id, file_path, operation, content, old_hash, new_hash, status,
                    created_at, expires_at, status_changed_at, applied_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.file_path,
                    proposal.operation.value,
                    proposal.content,
                    proposal.old_hash,
                    proposal.new_hash,
                    proposal.status.value,
                    _to_iso(proposal.created_at),
                    _to_iso(proposal.expires_at),
                    _optional_iso(proposal.status_changed_at),
                    _optional_iso(proposal.applied_at),
                ),
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
        row = self._connection.execute(
            "SELECT * FROM proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
        return _proposal_from_row(row) if row is not None else None

    def list(
        self,
        *,
        status: ProposalStatus | None = None,
        file_path: str | None = None,
        created_after: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Proposal, ...]:
        conditions: list[str] = []
        parameters: list[object] = []
        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value)
        if file_path is not None:
            conditions.append("file_path = ?")
            parameters.append(file_path)
        if created_after is not None:
            conditions.append("created_at >= ?")
            parameters.append(_to_iso(created_after))

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT *
            FROM proposals
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(_proposal_from_row(row) for row in rows)

    def expire_pending(self, now: datetime) -> int:
        expired_rows = self._connection.execute(
            """
            SELECT id
            FROM proposals
            WHERE status = ? AND expires_at <= ?
            ORDER BY created_at
            """,
            (ProposalStatus.PENDING.value, _to_iso(now)),
        ).fetchall()
        if not expired_rows:
            return 0

        with self.transaction():
            for row in expired_rows:
                proposal_id = row["id"]
                self._connection.execute(
                    """
                    UPDATE proposals
                    SET status = ?, status_changed_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (
                        ProposalStatus.EXPIRED.value,
                        _to_iso(now),
                        proposal_id,
                        ProposalStatus.PENDING.value,
                    ),
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
            cursor = self._connection.execute(
                """
                UPDATE proposals
                SET status = ?, status_changed_at = ?, applied_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ProposalStatus.APPLIED.value,
                    _to_iso(now),
                    _to_iso(now),
                    proposal_id,
                    ProposalStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
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
            cursor = self._connection.execute(
                """
                UPDATE proposals
                SET status = ?, status_changed_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ProposalStatus.REJECTED.value,
                    _to_iso(now),
                    proposal_id,
                    ProposalStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
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
            cursor = self._connection.execute(
                """
                UPDATE proposals
                SET status = ?, status_changed_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ProposalStatus.EXPIRED.value,
                    _to_iso(now),
                    proposal_id,
                    ProposalStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
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
        rows = self._connection.execute(
            """
            SELECT id, proposal_id, event_type, occurred_at, details
            FROM proposal_events
            WHERE proposal_id = ?
            ORDER BY id
            """,
            (proposal_id,),
        ).fetchall()
        return tuple(_event_from_row(row) for row in rows)

    def list_events(
        self,
        *,
        proposal_id: str | None = None,
        limit: int = 100,
    ) -> tuple[ProposalLifecycleEvent, ...]:
        if limit < 1:
            raise ValueError("Event list limit must be positive.")
        conditions: list[str] = []
        parameters: list[object] = []
        if proposal_id is not None:
            conditions.append("proposal_id = ?")
            parameters.append(proposal_id)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT id, proposal_id, event_type, occurred_at, details
            FROM proposal_events
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(_event_from_row(row) for row in rows)

    def cleanup_terminal(
        self,
        now: datetime,
        *,
        retention_days: int,
    ) -> int:
        cutoff = _to_iso(now - timedelta(days=retention_days))
        member_exclusion = """
        AND NOT EXISTS (
            SELECT 1
            FROM proposal_changeset_members
            WHERE proposal_changeset_members.proposal_id = proposals.id
        )
        """
        with self.transaction():
            cursor = self._connection.execute(
                f"""
                DELETE FROM proposals
                WHERE status IN (?, ?, ?)
                  AND COALESCE(status_changed_at, applied_at, created_at) <= ?
                  {member_exclusion}
                """,
                (
                    ProposalStatus.APPLIED.value,
                    ProposalStatus.REJECTED.value,
                    ProposalStatus.EXPIRED.value,
                    cutoff,
                ),
            )
        return int(cursor.rowcount)

    def delete_by_ids(self, proposal_ids: tuple[str, ...]) -> int:
        if not proposal_ids:
            return 0
        with self.transaction():
            removed = 0
            for proposal_id in proposal_ids:
                cursor = self._connection.execute(
                    "DELETE FROM proposals WHERE id = ?",
                    (proposal_id,),
                )
                removed += int(cursor.rowcount)
        return removed

    def _insert_event(
        self,
        proposal_id: str,
        event_type: str,
        occurred_at: datetime,
        details: dict[str, Any],
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO proposal_events (proposal_id, event_type, occurred_at, details)
            VALUES (?, ?, ?, ?)
            """,
            (
                proposal_id,
                event_type,
                _to_iso(occurred_at),
                json.dumps(details, sort_keys=True, separators=(",", ":")),
            ),
        )


def _proposal_from_row(row: sqlite3.Row) -> Proposal:
    return Proposal(
        proposal_id=row["id"],
        file_path=row["file_path"],
        operation=ProposalOperation(row["operation"]),
        content=row["content"],
        old_hash=row["old_hash"],
        new_hash=row["new_hash"],
        status=ProposalStatus(row["status"]),
        created_at=_from_iso(row["created_at"]),
        expires_at=_from_iso(row["expires_at"]),
        status_changed_at=_optional_from_iso(row["status_changed_at"]),
        applied_at=_optional_from_iso(row["applied_at"]),
    )


def _event_from_row(row: sqlite3.Row) -> ProposalLifecycleEvent:
    return ProposalLifecycleEvent(
        event_id=int(row["id"]),
        proposal_id=row["proposal_id"],
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
