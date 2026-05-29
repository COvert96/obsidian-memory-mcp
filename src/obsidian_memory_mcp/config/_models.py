from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar


@dataclass(frozen=True)
class ContextPackConfig:
    name: str
    paths: tuple[str, ...]
    description: str | None = None
    sections: tuple[str, ...] = ()
    tags_filter: tuple[str, ...] = ()
    include_context_packs: tuple[str, ...] = ()
    token_budget: int | None = None


@dataclass(frozen=True)
class AccessPolicy:
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()


@dataclass(frozen=True)
class AccessConstraints:
    read: AccessPolicy = field(default_factory=AccessPolicy)
    write: AccessPolicy = field(default_factory=AccessPolicy)


@dataclass(frozen=True)
class ProjectConfig:
    CONFIG_FILE_NAME: ClassVar[str] = "memory-mcp.yaml"
    DEFAULT_TAGS_SEPARATOR: ClassVar[str] = ","
    DEFAULT_MAX_WRITE_CONTENT_BYTES: ClassVar[int] = 1024 * 1024
    # Deprecated alias retained for the renamed write-size limit (Phase 8c).
    DEFAULT_MAX_PROPOSAL_CONTENT_BYTES: ClassVar[int] = DEFAULT_MAX_WRITE_CONTENT_BYTES
    DEFAULT_MEMORY_ARCHIVE_PATH: ClassVar[str] = "Memory/archive"

    vault_path: Path
    index_db_location: Path
    context_packs: tuple[ContextPackConfig, ...]
    write_constraints: AccessConstraints
    tags_separator: str = DEFAULT_TAGS_SEPARATOR
    max_write_content_bytes: int = DEFAULT_MAX_WRITE_CONTENT_BYTES
    memory_archive_path: str = DEFAULT_MEMORY_ARCHIVE_PATH


WritePolicy = AccessPolicy
WriteConstraints = AccessConstraints
