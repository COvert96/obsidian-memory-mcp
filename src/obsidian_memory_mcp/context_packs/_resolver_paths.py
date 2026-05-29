"""Path resolution helpers for context-pack document loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePath

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ToolExecutionError

_GLOB_CHARS = frozenset("*?[")


@dataclass(frozen=True)
class ExplicitPathResolution:
    absolute_path: Path | None = None
    missing_file: str | None = None
    warning: str | None = None


def contains_glob(pattern: str) -> bool:
    return any(character in pattern for character in _GLOB_CHARS)


def normalize_vault_reference(value: str) -> str:
    return value.replace("\\", "/").lstrip("/")


def is_unsafe_pattern(pattern: str) -> bool:
    path = PurePath(pattern)
    return path.is_absolute() or ".." in path.parts


def has_symlink_segment(vault_root: Path, path: Path) -> bool:
    try:
        relative_parts = path.relative_to(vault_root).parts
    except ValueError:
        return True

    current = vault_root
    for part in relative_parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def resolve_explicit_path(
    config: ProjectConfig,
    guardrails: GuardrailEvaluator,
    pattern: str,
) -> ExplicitPathResolution:
    path = normalize_vault_reference(pattern)
    if is_unsafe_pattern(path):
        return ExplicitPathResolution(
            warning=f"Path '{path}' was skipped because it is unsafe."
        )
    if not guardrails.allows_read_relative(path):
        return ExplicitPathResolution(
            warning=f"File '{path}' was skipped because it violates read guardrails."
        )

    absolute_path = config.vault_path / path
    if not absolute_path.is_file():
        return ExplicitPathResolution(missing_file=path)
    return ExplicitPathResolution(absolute_path=absolute_path)


def expand_glob(
    config: ProjectConfig, pattern: str
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    normalized = normalize_vault_reference(pattern)
    if is_unsafe_pattern(normalized):
        return (), (f"Path pattern '{normalized}' was skipped because it is unsafe.",)

    matches = sorted(
        (path for path in config.vault_path.glob(normalized) if path.is_file()),
        key=lambda path: path.relative_to(config.vault_path).as_posix(),
    )
    return tuple(matches), ()


def guard_read_path(
    config: ProjectConfig,
    guardrails: GuardrailEvaluator,
    absolute_path: Path,
) -> tuple[Path | None, str | None]:
    """Return a resolved absolute path, or a warning when the path must be skipped."""
    vault_path = absolute_path.relative_to(config.vault_path).as_posix()
    if not guardrails.allows_read_relative(vault_path):
        return None, (
            f"File '{vault_path}' was skipped because it violates read guardrails."
        )
    if not has_symlink_segment(config.vault_path, absolute_path):
        return absolute_path, None

    try:
        return guardrails.check_read(vault_path), None
    except ToolExecutionError as error:
        return None, f"Path '{vault_path}' was skipped: {error.error.message}"
