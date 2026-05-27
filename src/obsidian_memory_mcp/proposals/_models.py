"""Data models for guarded write proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProposalOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    file_path: str
    operation: ProposalOperation
    content: str | None
    old_hash: str | None
    new_hash: str | None
    status: ProposalStatus
    created_at: datetime
    expires_at: datetime
    status_changed_at: datetime | None = None
    applied_at: datetime | None = None


@dataclass(frozen=True)
class ProposalCreateResult:
    proposal_id: str
    file_path: str
    operation: ProposalOperation
    old_hash: str | None
    new_hash: str | None
    ttl_seconds: int

    def as_response(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "file_path": self.file_path,
            "operation": self.operation.value,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "ttl_seconds": self.ttl_seconds,
        }


@dataclass(frozen=True)
class ProposalListItem:
    proposal_id: str
    file_path: str
    operation: ProposalOperation
    status: ProposalStatus
    created_at: datetime
    expires_at: datetime
    old_hash: str | None
    new_hash: str | None
    preview: str | None

    def as_response(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "file_path": self.file_path,
            "operation": self.operation.value,
            "status": self.status.value,
            "created_at": _isoformat(self.created_at),
            "expires_at": _isoformat(self.expires_at),
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "preview": self.preview,
        }


@dataclass(frozen=True)
class ProposalApprovalResult:
    proposal_id: str
    file_path: str
    operation: ProposalOperation
    status: ProposalStatus
    written_at: datetime
    file_size_bytes: int

    def as_response(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "file_path": self.file_path,
            "operation": self.operation.value,
            "status": self.status.value,
            "written_at": _isoformat(self.written_at),
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass(frozen=True)
class ProposalRejectionResult:
    proposal_id: str
    file_path: str
    operation: ProposalOperation
    status: ProposalStatus
    rejected_at: datetime

    def as_response(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "file_path": self.file_path,
            "operation": self.operation.value,
            "status": self.status.value,
            "rejected_at": _isoformat(self.rejected_at),
        }


@dataclass(frozen=True)
class ProposalLifecycleEvent:
    event_id: int
    proposal_id: str
    event_type: str
    occurred_at: datetime
    details: dict[str, Any]


def _isoformat(value: datetime) -> str:
    return value.isoformat()
