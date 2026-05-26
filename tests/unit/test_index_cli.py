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
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )


def test_index_cli_runs_incremental_status_errors_and_debug_search(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    (vault / "note.md").write_text(
        "---\n: broken\n---\n# Note\nneedle body", encoding="utf-8"
    )

    index_exit = main(["index", str(vault)])
    status_exit = main(["index", "status", str(vault)])
    errors_exit = main(["index", "errors", str(vault)])
    search_exit = main(["debug", "search", str(vault), "needle", "--json"])
    output = capsys.readouterr().out

    assert index_exit == 2
    assert status_exit == 0
    assert errors_exit == 0
    assert search_exit == 0
    assert "success_with_errors" in output
    assert "malformed YAML" in output
    assert '"query": "needle"' in output


def test_full_index_cli_requires_confirmation_unless_yes_is_passed(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    (vault / "note.md").write_text("# Note\nbody", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")

    cancelled = main(["index", "--full", str(vault)])
    confirmed = main(["index", "--full", "--yes", str(vault)])

    assert cancelled == 1
    assert confirmed == 0
    assert "cancelled" in capsys.readouterr().out.lower()


def test_index_cli_returns_guardrail_exit_code_for_invalid_config(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    exit_code = main(["index", str(vault)])

    assert exit_code == 3
    assert "Config is invalid" in capsys.readouterr().out


def test_debug_search_cli_reports_malformed_query_without_traceback(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    (vault / "note.md").write_text("# Note\nbody", encoding="utf-8")
    assert main(["index", "--full", "--yes", str(vault)]) == 0

    exit_code = main(["debug", "search", str(vault), "AND"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "Invalid debug search query" in output


def test_index_and_debug_help_text_exists(capsys) -> None:
    assert main(["index", "--help"]) == 0
    assert main(["debug", "search", "--help"]) == 0
    output = capsys.readouterr().out

    assert "mcp-memory index" in output
    assert "mcp-memory debug search" in output
