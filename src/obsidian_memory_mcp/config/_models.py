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
    DEFAULT_MAX_PROPOSAL_TTL_HOURS: ClassVar[int] = 24
    DEFAULT_PROPOSAL_TTL_SECONDS: ClassVar[int] = 3600
    DEFAULT_MAX_WRITE_CONTENT_BYTES: ClassVar[int] = 1024 * 1024
    DEFAULT_MAX_PROPOSAL_CONTENT_BYTES: ClassVar[int] = 1024 * 1024  # deprecated alias
    DEFAULT_PROPOSAL_RETENTION_DAYS: ClassVar[int] = 7

    vault_path: Path
    index_db_location: Path
    context_packs: tuple[ContextPackConfig, ...]
    write_constraints: AccessConstraints
    tags_separator: str = DEFAULT_TAGS_SEPARATOR
    max_proposal_ttl_hours: int = DEFAULT_MAX_PROPOSAL_TTL_HOURS
    proposal_ttl_seconds: int = DEFAULT_PROPOSAL_TTL_SECONDS
    max_write_content_bytes: int = DEFAULT_MAX_WRITE_CONTENT_BYTES
    proposal_retention_days: int = DEFAULT_PROPOSAL_RETENTION_DAYS


WritePolicy = AccessPolicy
WriteConstraints = AccessConstraints
