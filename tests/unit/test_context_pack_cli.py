from __future__ import annotations

from pathlib import Path

from obsidian_memory_mcp.cli import main


def _write_config(vault: Path) -> None:
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: default
    description: "Default docs"
    paths: ["docs/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )


def test_pack_cli_lists_validates_and_loads_context_packs(
    tmp_path: Path,
    capsys,
) -> None:
    vault = tmp_path / "vault"
    (vault / "docs").mkdir(parents=True)
    (vault / "docs" / "guide.md").write_text("# Guide\nBody.", encoding="utf-8")
    _write_config(vault)

    list_exit = main(["pack", "list", str(vault)])
    validate_exit = main(["pack", "validate", "default", str(vault)])
    load_exit = main(["pack", "load", "default", str(vault)])
    output = capsys.readouterr().out

    assert list_exit == 0
    assert validate_exit == 0
    assert load_exit == 0
    assert "default" in output
    assert "Default docs" in output
    assert "Files included:" in output
    assert "Token count:" in output
    assert "Duration ms:" in output
    assert "<!-- From: docs/guide.md -->" in output


def test_pack_validate_returns_error_for_missing_files(
    tmp_path: Path,
    capsys,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: broken
    paths: ["missing.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )

    exit_code = main(["pack", "validate", "broken", str(vault)])

    assert exit_code == 1
    assert "Missing files:" in capsys.readouterr().out
