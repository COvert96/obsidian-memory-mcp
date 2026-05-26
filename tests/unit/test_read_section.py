from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader, GuardrailEvaluator
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.retrieval import ReadSectionService


def _service(vault: Path) -> ReadSectionService:
    config = ConfigLoader(vault).load()
    return ReadSectionService(config, GuardrailEvaluator(config))


def test_read_section_returns_heading_body_nested_headings_and_context(
    vault_root: Path,
) -> None:
    note = vault_root / "wiki" / "guide.md"
    note.write_text(
        "# Product\n"
        "Context one.\n"
        "Context two.\n"
        "Context three.\n"
        "## Installation\n"
        "Install the package.\n"
        "### Windows\n"
        "Use PowerShell.\n"
        "## API Reference\n"
        "Call the API.\n",
        encoding="utf-8",
    )

    result = _service(vault_root).read("wiki/guide.md", "installation")

    assert result == {
        "file_path": "wiki/guide.md",
        "heading": "Installation",
        "heading_level": 2,
        "content": (
            "## Installation\n"
            "Install the package.\n"
            "### Windows\n"
            "Use PowerShell."
        ),
        "context_prefix": "Context one.\nContext two.\nContext three.",
    }


def test_read_section_context_is_empty_when_heading_follows_frontmatter(
    vault_root: Path,
) -> None:
    note = vault_root / "wiki" / "frontmatter.md"
    note.write_text("---\ntags: [api]\n---\n\n# Overview\nBody.\n", encoding="utf-8")

    result = _service(vault_root).read("wiki/frontmatter.md", "overview")

    assert result["content"] == "# Overview\nBody."
    assert result["context_prefix"] == ""


def test_read_section_ignores_heading_markers_inside_fenced_code(
    vault_root: Path,
) -> None:
    note = vault_root / "wiki" / "code.md"
    note.write_text(
        "# Real\n"
        "```md\n"
        "## Fake\n"
        "```\n"
        "Still real.\n"
        "# Next\n"
        "Done.\n",
        encoding="utf-8",
    )

    result = _service(vault_root).read("wiki/code.md", "real")

    assert "## Fake" in result["content"]
    assert "# Next" not in result["content"]


def test_read_section_raises_section_not_found(vault_root: Path) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault_root).read("wiki/concept.md", "Missing")

    assert exc_info.value.error.code is ErrorCode.ERR_SECTION_NOT_FOUND


def test_read_section_raises_missing_file(vault_root: Path) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault_root).read("wiki/missing.md", "Anything")

    assert exc_info.value.error.code is ErrorCode.ERR_MISSING_FILE
