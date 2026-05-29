from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.utils import normalize_vault_path


def assert_guardrail_violation(vault: Path, requested_path: str) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        normalize_vault_path(vault, requested_path)

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION
    assert exc_info.value.error.message


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    vault_path = tmp_path / "vault"
    (vault_path / "wiki" / "nested").mkdir(parents=True)
    (vault_path / "wiki" / "note.md").write_text("# Note\n", encoding="utf-8")
    (vault_path / "wiki" / "nested" / "note.md").write_text(
        "# Nested\n", encoding="utf-8"
    )
    (tmp_path / "sibling_vault").mkdir()
    return vault_path


@pytest.mark.parametrize(
    "requested_path",
    [
        "../../etc/passwd",
        "../vault/wiki/note.md",
        "wiki/../../outside.md",
        "wiki/nested/../note.md",
        "wiki/%2e%2e/outside.md",
        "wiki/%2E%2E/outside.md",
        "wiki/..",
        "./../sibling_vault",
        "vault_root/../sibling_vault",
        "wiki\\..\\outside.md",
        "..\\..\\Windows\\win.ini",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "C:\\Windows\\win.ini",
        "//server/share/file.md",
        "",
    ],
)
def test_traversal_attempts_are_blocked(vault: Path, requested_path: str) -> None:
    assert_guardrail_violation(vault, requested_path)


def test_absolute_path_inside_vault_is_allowed(vault: Path) -> None:
    requested_path = vault / "wiki" / "note.md"

    resolved_path = normalize_vault_path(vault, str(requested_path))

    assert resolved_path == requested_path.resolve()


@pytest.mark.parametrize(
    "requested_path",
    [
        "wiki/note.md",
        ".",
        "./wiki/note.md",
        "wiki/nested/",
        "wiki//note.md",
    ],
)
def test_legitimate_paths_are_normalized(vault: Path, requested_path: str) -> None:
    resolved_path = normalize_vault_path(vault, requested_path)

    assert resolved_path.is_relative_to(vault.resolve())


def test_symlink_to_outside_vault_is_blocked(vault: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = vault / "wiki" / "outside-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are not available in this environment.")

    assert_guardrail_violation(vault, "wiki/outside-link")


def test_symlink_inside_vault_is_allowed(vault: Path) -> None:
    target = vault / "wiki" / "nested"
    link = vault / "nested-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are not available in this environment.")

    assert normalize_vault_path(vault, "nested-link") == target.resolve()
