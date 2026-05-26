"""Tests for server-level project registry loading and resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.server_registry import (
    load_project_registry,
)


# ---------------------------------------------------------------------------
# ProjectRegistry.resolve
# ---------------------------------------------------------------------------


def test_resolve_returns_vault_root_for_known_project(
    registry_path: Path, vault_root: Path
) -> None:
    registry = load_project_registry(registry_path)
    assert registry.resolve("alpha") == vault_root.resolve()


def test_resolve_raises_for_unknown_project(registry_path: Path) -> None:
    registry = load_project_registry(registry_path)

    with pytest.raises(ToolExecutionError) as exc_info:
        registry.resolve("no-such-project")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_PROJECT
    assert "no-such-project" in error.message
    assert "alpha" in error.details["known_projects"]


def test_projects_mapping_is_immutable(registry_path: Path) -> None:
    registry = load_project_registry(registry_path)

    with pytest.raises(TypeError):
        registry.projects["injected"] = Path("/tmp")  # type: ignore[index]


# ---------------------------------------------------------------------------
# load_project_registry — file-level failures
# ---------------------------------------------------------------------------


def test_load_raises_when_registry_file_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-file.yaml"

    with pytest.raises(ToolExecutionError) as exc_info:
        load_project_registry(missing)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_PROJECT
    assert "not found" in exc_info.value.error.message


def test_load_raises_when_registry_yaml_is_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "registry.yaml"
    bad.write_text("projects: [\nunterminated", encoding="utf-8")

    with pytest.raises(ToolExecutionError) as exc_info:
        load_project_registry(bad)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_PROJECT
    assert "malformed YAML" in exc_info.value.error.message


def test_load_raises_when_projects_key_is_missing(tmp_path: Path) -> None:
    bad = tmp_path / "registry.yaml"
    bad.write_text("not_projects:\n  alpha: /tmp\n", encoding="utf-8")

    with pytest.raises(ToolExecutionError) as exc_info:
        load_project_registry(bad)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_PROJECT


def test_load_raises_when_vault_path_is_relative(tmp_path: Path) -> None:
    bad = tmp_path / "registry.yaml"
    bad.write_text("projects:\n  alpha: relative/path\n", encoding="utf-8")

    with pytest.raises(ToolExecutionError) as exc_info:
        load_project_registry(bad)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_PROJECT


def test_load_raises_when_vault_directory_does_not_exist(tmp_path: Path) -> None:
    missing_vault = tmp_path / "nonexistent-vault"
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(
        f'projects:\n  alpha: "{missing_vault.as_posix()}"\n',
        encoding="utf-8",
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        load_project_registry(registry_file)

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_PROJECT
    assert "not an existing directory" in error.message
