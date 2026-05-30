"""Helpers for copying the committed sample vault in integration tests."""

from __future__ import annotations

import shutil
from pathlib import Path

SAMPLE_VAULT_SOURCE = Path(__file__).parent / "sample-vault"


def write_sample_vault_config(vault: Path) -> None:
    """Write memory-mcp.yaml with vault_path set to *vault* (absolute)."""
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""vault_path: "{vault.resolve().as_posix()}"
index_db_location: "memory-index.sqlite3"

context_packs:
  - name: "default"
    paths:
      - "wiki/**/*.md"
    token_budget: 8000
  - name: "tight-budget"
    description: "Intentionally small budget for over-budget UAT tests (TC-GCP-02, TC-GCP-03)"
    paths:
      - "wiki/**/*.md"
    token_budget: 50
write_constraints:
  read:
    allow:
      - "wiki/**"
      - "Memory/**"
    deny:
      - "wiki/private/**"
  write:
    allow:
      - "Memory/**"
      - "wiki/concepts/"
max_write_content_bytes: 1048576
memory_archive_path: "Memory/archive"
""",
        encoding="utf-8",
    )


def copy_sample_vault(destination: Path) -> Path:
    """Copy the committed sample vault tree and write a portable config file."""
    shutil.copytree(SAMPLE_VAULT_SOURCE, destination)
    write_sample_vault_config(destination)
    return destination
