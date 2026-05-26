from __future__ import annotations

from pathlib import Path
from typing import Any

from obsidian_memory_mcp.config.model import (
    AccessConstraints,
    AccessPolicy,
    ContextPackConfig,
)


def resolve_config_path(vault_path: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (vault_path / path).resolve(strict=False)


def parse_context_packs(data: list[dict[str, Any]]) -> tuple[ContextPackConfig, ...]:
    return tuple(
        ContextPackConfig(
            name=context_pack["name"],
            paths=tuple(context_pack["paths"]),
            description=context_pack.get("description"),
            sections=tuple(context_pack.get("sections", ())),
            tags_filter=tuple(context_pack.get("tags_filter", ())),
            include_context_packs=tuple(context_pack.get("include_context_packs", ())),
            token_budget=context_pack.get("token_budget"),
        )
        for context_pack in data
    )


def parse_write_constraints(data: dict[str, Any]) -> AccessConstraints:
    return AccessConstraints(
        read=parse_access_policy(data.get("read", {})),
        write=parse_access_policy(data.get("write", {})),
    )


def parse_access_policy(data: dict[str, Any]) -> AccessPolicy:
    return AccessPolicy(
        allow=tuple(data.get("allow", ())),
        deny=tuple(data.get("deny", ())),
    )
