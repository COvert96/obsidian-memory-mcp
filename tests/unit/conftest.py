"""Shared pytest fixtures for the unit-test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


_MINIMAL_VAULT_CONFIG = """\
vault_path: "{vault}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: default
    paths: ["README.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
"""


@pytest.fixture()
def vault_root(tmp_path: Path) -> Path:
    """A minimal, valid Obsidian vault with a config file and one note."""
    root = tmp_path / "vault"
    (root / "wiki").mkdir(parents=True)
    root.joinpath("memory-mcp.yaml").write_text(
        _MINIMAL_VAULT_CONFIG.format(vault=root.as_posix()),
        encoding="utf-8",
    )
    root.joinpath("wiki", "concept.md").write_text(
        "---\ntype: concept\n---\n# Concept\nBody text.\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def registry_path(tmp_path: Path, vault_root: Path) -> Path:
    """A registry file mapping project 'alpha' to *vault_root*."""
    path = tmp_path / "memory-mcp-server.yaml"
    path.write_text(
        f'projects:\n  alpha: "{vault_root.as_posix()}"\n',
        encoding="utf-8",
    )
    return path
