from __future__ import annotations

import os
from pathlib import Path

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.search_debug import debug_search
from obsidian_memory_mcp.status import get_index_status


def _config(vault: Path):
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["wiki/**/*.md"]
write_constraints:
  read:
    allow: ["wiki/**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )
    return ConfigLoader(vault).load()


def test_indexing_workflow_covers_full_incremental_delete_reappear_parser_drift_and_metadata_drift(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / ".mcp").mkdir()
    alpha = vault / "wiki" / "alpha.md"
    beta = vault / "wiki" / "beta.md"
    broken = vault / "wiki" / "broken.md"
    alpha.write_text(
        "---\ntags: [alpha]\n---\n# Alpha\ninitial searchable", encoding="utf-8"
    )
    beta.write_text("# Beta\nstable searchable", encoding="utf-8")
    config = _config(vault)

    full = run_index(config, mode=IndexMode.FULL)
    no_changes = run_index(config)
    alpha.write_text(
        "---\ntags: [alpha]\n---\n# Alpha\nchanged searchable", encoding="utf-8"
    )
    changed = run_index(config)
    beta.unlink()
    deleted = run_index(config)
    drift = get_index_status(config, parser_version="future-parser")
    broken.write_text(
        "---\n: broken\n---\n# Broken\nstill searchable", encoding="utf-8"
    )
    malformed = run_index(config)
    beta.write_text("# Beta\nreturned searchable", encoding="utf-8")
    reappeared = run_index(config)
    next_mtime = beta.stat().st_mtime + 10
    os.utime(beta, (next_mtime, next_mtime))
    metadata_drift = run_index(config)

    assert full.files_processed == 2
    assert no_changes.files_skipped == 2
    assert changed.files_processed == 1
    assert deleted.files_deleted == 1
    assert drift.parser_version_drift == 1
    assert malformed.status == "success_with_errors"
    assert malformed.files_processed == 1
    assert reappeared.files_processed == 1
    assert metadata_drift.files_skipped == 3
    assert [
        result.vault_path for result in debug_search(config, "returned", limit=5)
    ] == ["wiki/beta.md"]
