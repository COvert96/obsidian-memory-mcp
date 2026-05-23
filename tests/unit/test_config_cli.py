from __future__ import annotations

from pathlib import Path

from obsidian_memory_mcp.cli import main


def test_config_validate_cli_reports_valid_config(tmp_path: Path, capsys) -> None:
    (tmp_path / "memory-mcp.yaml").write_text(
        """
vault_path: "{vault}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: default
    paths: ["README.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["wiki/proposals/"]
""".format(vault=tmp_path.as_posix()),
        encoding="utf-8",
    )

    exit_code = main(["config", "validate", str(tmp_path)])

    assert exit_code == 0
    assert "Config is valid" in capsys.readouterr().out


def test_config_validate_cli_reports_all_validation_errors(tmp_path: Path, capsys) -> None:
    (tmp_path / "memory-mcp.yaml").write_text(
        """
vault_path: relative/path
context_packs: prd
""",
        encoding="utf-8",
    )

    exit_code = main(["config", "validate", str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "vault_path" in output
    assert "index_db_location" in output
    assert "write_constraints" in output
