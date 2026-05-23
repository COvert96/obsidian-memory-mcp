from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILE_NAME = "memory-mcp.yaml"
DEFAULT_TAGS_SEPARATOR = ","
DEFAULT_MAX_PROPOSAL_TTL_HOURS = 24


@dataclass(frozen=True)
class ContextPackConfig:
    name: str
    paths: tuple[str, ...]
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
    vault_path: Path
    index_db_location: Path
    context_packs: tuple[ContextPackConfig, ...]
    write_constraints: AccessConstraints
    tags_separator: str = DEFAULT_TAGS_SEPARATOR
    max_proposal_ttl_hours: int = DEFAULT_MAX_PROPOSAL_TTL_HOURS


WritePolicy = AccessPolicy
WriteConstraints = AccessConstraints
