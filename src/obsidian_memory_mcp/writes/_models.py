"""WriteResult — the return value of WriteService.create()."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class WriteResult:
    file_path: str
    operation: str
    content_hash: str
    file_size_bytes: int
    written_at: datetime

    def as_response(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "operation": self.operation,
            "content_hash": self.content_hash,
            "file_size_bytes": self.file_size_bytes,
            "written_at": self.written_at.isoformat(),
        }
