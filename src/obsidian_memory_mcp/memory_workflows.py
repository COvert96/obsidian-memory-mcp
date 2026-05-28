"""Memory-specific workflows built on grouped proposal changesets."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

import yaml

from obsidian_memory_mcp.changesets import (
    ChangesetApprovalResult,
    ChangesetCreateResult,
    ChangesetManager,
    ChangesetReview,
    FileMutation,
)
from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


class MemorySupersessionWorkflow:
    def __init__(
        self,
        config: ProjectConfig,
        guardrails: GuardrailEvaluator | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        changeset_id_factory: Callable[[], str] | None = None,
        proposal_id_factory: Callable[[], str] | None = None,
    ):
        self._config = config
        self._guardrails = guardrails or GuardrailEvaluator(config)
        self._clock = clock or _utc_now
        self._changesets = ChangesetManager(
            config,
            self._guardrails,
            clock=self._clock,
            id_factory=changeset_id_factory,
            proposal_id_factory=proposal_id_factory,
        )

    def propose_supersession(
        self,
        *,
        superseded_file_path: str,
        new_file_path: str,
        new_content: str,
    ) -> ChangesetCreateResult:
        old_path = _normalize_memory_path(superseded_file_path)
        successor_path = _normalize_memory_path(new_file_path)
        if old_path == successor_path:
            raise _semantic_contradiction_error(
                "A semantic contradiction workflow needs distinct old and new notes."
            )

        archived_at = self._now().isoformat()
        old_target = self._guardrails.check_write(old_path)
        if not old_target.is_file():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_MISSING_FILE,
                    details={"file_path": old_path},
                )
            )

        old_content = old_target.read_text(encoding="utf-8")
        superseded_content = _merge_frontmatter(
            old_content,
            {
                "status": "superseded",
                "superseded_by": successor_path,
                "archived_at": archived_at,
            },
        )
        active_content = _merge_frontmatter(
            new_content,
            {
                "status": "active",
                "supersedes": [old_path],
            },
        )

        return self._changesets.create(
            title=f"Supersede {old_path}",
            description=(
                "Semantic contradiction supersession: preserve the prior memory "
                "note and publish a new active source of truth."
            ),
            mutations=(
                FileMutation(old_path, "update", superseded_content),
                FileMutation(successor_path, "create", active_content),
            ),
        )

    def review(self, changeset_id: str) -> ChangesetReview:
        return self._changesets.review(changeset_id)

    def approve(
        self,
        changeset_id: str,
        *,
        actor: str | None = "operator",
    ) -> ChangesetApprovalResult:
        return self._changesets.approve(changeset_id, actor=actor)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _normalize_memory_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").strip().lstrip("/")
    path = PurePosixPath(normalized)
    if len(path.parts) >= 2 and path.parts[0] == "Memory":
        return path.as_posix()
    raise ToolExecutionError(
        build_error(
            ErrorCode.ERR_INVALID_REQUEST,
            message=(
                "Memory supersession only supports files under 'Memory/'. "
                f"Received '{file_path}'."
            ),
            details={"file_path": file_path, "required_prefix": "Memory/"},
        )
    )


def _merge_frontmatter(content: str, updates: dict[str, Any]) -> str:
    metadata, body = _split_frontmatter(content)
    merged = {**metadata, **updates}
    return f"---\n{_render_frontmatter(merged)}---\n{body}"


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            raw_metadata = "".join(lines[1:index])
            loaded = yaml.safe_load(raw_metadata) if raw_metadata.strip() else {}
            metadata = loaded if isinstance(loaded, dict) else {}
            return dict(metadata), "".join(lines[index + 1 :])
    return {}, content


def _render_frontmatter(metadata: dict[str, Any]) -> str:
    rendered = []
    for key, value in metadata.items():
        if isinstance(value, list):
            rendered.append(f"{key}:")
            for item in value:
                _ensure_supported_frontmatter_value(key, item)
                rendered.append(f"  - {_format_scalar(item)}")
            continue
        _ensure_supported_frontmatter_value(key, value)
        rendered.append(f"{key}: {_format_scalar(value)}")
    return "\n".join(rendered) + "\n"


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int | float):
        return str(value)

    text = str(value)
    if _needs_yaml_quotes(text):
        escaped = text.replace("'", "''")
        return f"'{escaped}'"
    return text


def _needs_yaml_quotes(text: str) -> bool:
    if text == "" or text.strip() != text:
        return True
    normalized = text.lower()
    if normalized in {
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        "null",
        "~",
    }:
        return True
    if text[0] in "-?:,[]{}#&*!|>'\"%@`":
        return True
    return any(character in text for character in ":#{}[]>,|*&!%@`")


def _ensure_supported_frontmatter_value(key: str, value: Any) -> None:
    if isinstance(value, str | bool | int | float) or value is None:
        return
    raise ToolExecutionError(
        build_error(
            ErrorCode.ERR_INVALID_REQUEST,
            message=(
                "Memory supersession frontmatter does not support nested values "
                f"for key '{key}'."
            ),
            details={"field": key, "value_type": type(value).__name__},
        )
    )


def _semantic_contradiction_error(message: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(
            ErrorCode.ERR_INVALID_REQUEST,
            message=f"Invalid semantic contradiction workflow: {message}",
            details={"conflict_type": "semantic_contradiction"},
        )
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
