from __future__ import annotations

from pathlib import Path

from obsidian_memory_mcp.config import (
    AccessConstraints,
    AccessPolicy,
    ContextPackConfig,
    ProjectConfig,
)
from obsidian_memory_mcp.context_packs import ContextPackLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index


def _config(
    vault: Path,
    pack: ContextPackConfig,
) -> ProjectConfig:
    return ProjectConfig(
        vault_path=vault,
        index_db_location=vault / "memory-index.sqlite3",
        context_packs=(pack,),
        write_constraints=AccessConstraints(read=AccessPolicy(allow=("**/*.md",))),
    )


def test_soft_budget_truncates_at_complete_section_boundary(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "guide.md").write_text(
        "# First\nx x x x x\n\n# Second\n" + "y " * 200,
        encoding="utf-8",
    )
    config = _config(
        vault,
        ContextPackConfig(name="guide", paths=("guide.md",), token_budget=20),
    )

    result = ContextPackLoader(config).load("guide", strict_budget=False)

    assert result.token_count <= 20
    assert "# First" in result.content
    assert "# Second" not in result.content
    assert result.content.rstrip().endswith("x x x x x")
    assert any("truncated" in warning for warning in result.warnings)


def test_soft_budget_preserves_contiguous_sections_when_later_fragment_fits(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "guide.md").write_text(
        "# First\nx x x\n\n# Oversized\n" + "y " * 200 + "\n\n# Third\nz z z",
        encoding="utf-8",
    )
    config = _config(
        vault,
        ContextPackConfig(name="guide", paths=("guide.md",), token_budget=25),
    )

    result = ContextPackLoader(config).load("guide", strict_budget=False)

    assert "# First" in result.content
    assert "# Oversized" not in result.content
    assert "# Third" not in result.content


def test_soft_budget_emits_at_most_one_near_budget_warning_after_truncation(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "guide.md").write_text(
        "# First\n" + "x " * 20 + "\n\n# Second\n" + "y " * 200,
        encoding="utf-8",
    )
    config = _config(
        vault,
        ContextPackConfig(name="guide", paths=("guide.md",), token_budget=35),
    )

    result = ContextPackLoader(config).load("guide", strict_budget=False)
    near_budget_warnings = [
        warning for warning in result.warnings if "near its token budget" in warning
    ]

    assert len(near_budget_warnings) <= 1


def test_soft_budget_prefers_bm25_ranked_files_before_truncating(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "api").mkdir(parents=True)
    (vault / "api" / "a-general.md").write_text(
        "# General\n" + "general " * 40,
        encoding="utf-8",
    )
    (vault / "api" / "z-api.md").write_text(
        "# API\napi api api\n",
        encoding="utf-8",
    )
    config = _config(
        vault,
        ContextPackConfig(name="api", paths=("api/*.md",), token_budget=18),
    )
    run_index(config, mode=IndexMode.FULL)

    result = ContextPackLoader(config).load("api", strict_budget=False)

    assert "api/z-api.md" in result.files_included
    assert "api/a-general.md" not in result.files_included
    assert "<!-- From: api/z-api.md -->" in result.content
    assert "<!-- From: api/a-general.md -->" not in result.content
