from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path

import pytest

from obsidian_memory_mcp.config import (
    AccessConstraints,
    AccessPolicy,
    ContextPackConfig,
    ProjectConfig,
)
from obsidian_memory_mcp.context_packs import ContextPackLoader
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.parser import PARSER_VERSION
from obsidian_memory_mcp.database import connect_index_db
from obsidian_memory_mcp.migrations import ensure_index_migrated


def _config(
    vault: Path,
    packs: tuple[ContextPackConfig, ...],
) -> ProjectConfig:
    return ProjectConfig(
        vault_path=vault,
        index_db_location=vault / "memory-index.sqlite3",
        context_packs=packs,
        write_constraints=AccessConstraints(read=AccessPolicy(allow=("**/*.md",))),
    )


def test_loader_concatenates_paths_sections_tags_and_includes_in_order(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "docs" / "api").mkdir(parents=True)
    (vault / "docs" / "api" / "one.md").write_text(
        "---\ntags: [api, public]\n---\n"
        "# Overview\nOne overview.\n"
        "# Details\nPrivate details.\n",
        encoding="utf-8",
    )
    (vault / "docs" / "api" / "private.md").write_text(
        "---\ntags: [internal]\n---\n# Overview\nDo not include.",
        encoding="utf-8",
    )
    (vault / "docs" / "api" / "two.md").write_text(
        "---\ntags: [api]\n---\n# Overview\nTwo overview.",
        encoding="utf-8",
    )
    (vault / "README.md").write_text("# Foundation\nBase context.", encoding="utf-8")
    config = _config(
        vault,
        (
            ContextPackConfig(
                name="api",
                paths=("docs/api/*.md",),
                sections=("overview",),
                tags_filter=("api",),
                include_context_packs=("foundation",),
            ),
            ContextPackConfig(name="foundation", paths=("README.md",)),
        ),
    )

    result = ContextPackLoader(config).load("api")

    assert list(result.files_included) == [
        "docs/api/one.md",
        "docs/api/two.md",
        "README.md",
    ]
    assert result.missing_files == ()
    assert result.warnings == ()
    assert result.content == (
        "<!-- From: docs/api/one.md -->\n"
        "# Overview\nOne overview.\n\n"
        "<!-- From: docs/api/two.md -->\n"
        "# Overview\nTwo overview.\n\n"
        "<!-- From: README.md -->\n"
        "# Foundation\nBase context.\n\n"
    )


def test_loader_keeps_found_sections_when_some_requested_sections_are_missing(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "guide.md").write_text(
        "# Overview\nPublic overview.\n# Private\nDo not include.",
        encoding="utf-8",
    )
    config = _config(
        vault,
        (
            ContextPackConfig(
                name="guide",
                paths=("guide.md",),
                sections=("Overview", "Typo"),
            ),
        ),
    )

    result = ContextPackLoader(config).load("guide")

    assert "# Overview\nPublic overview." in result.content
    assert "# Private" not in result.content
    assert (
        "Sections not found in 'guide.md': Typo; included available sections only."
        in result.warnings
    )


def test_loader_ignores_markdown_headings_inside_nested_fenced_code(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "code.md").write_text(
        "# Real\n```md\n````python\n# Fake\n```\nStill real.\n# Next\nDone.\n",
        encoding="utf-8",
    )
    config = _config(
        vault,
        (ContextPackConfig(name="code", paths=("code.md",), sections=("Real",)),),
    )

    result = ContextPackLoader(config).load("code")

    assert "# Fake" in result.content
    assert "# Next" not in result.content


def test_loader_does_not_warn_stale_when_indexed_at_matches_mtime_ns(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "fresh.md"
    note.write_text("# Fresh\nBody.", encoding="utf-8")
    base_seconds = int(datetime(2026, 5, 26, 10, tzinfo=UTC).timestamp())
    mtime_ns = base_seconds * 1_000_000_000 + 123_456_789
    os.utime(note, ns=(mtime_ns, mtime_ns))
    config = _config(
        vault,
        (ContextPackConfig(name="fresh", paths=("fresh.md",)),),
    )
    _insert_indexed_file(
        config,
        "fresh.md",
        indexed_at="2026-05-26T10:00:00.123456789+00:00",
        mtime_ns=mtime_ns,
    )

    result = ContextPackLoader(config).load("fresh")

    assert not any(
        "modified since last index" in warning for warning in result.warnings
    )


def test_loader_reports_missing_files_missing_sections_and_stale_files(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "docs").mkdir(parents=True)
    stale = vault / "docs" / "stale.md"
    stale.write_text("# Context\nChanged since index.", encoding="utf-8")
    config = _config(
        vault,
        (
            ContextPackConfig(
                name="ops",
                paths=("docs/missing.md", "docs/stale.md"),
                sections=("Decision",),
            ),
        ),
    )
    _insert_indexed_file(
        config, "docs/stale.md", indexed_at="1970-01-01T00:00:00+00:00"
    )

    result = ContextPackLoader(config).load("ops")

    assert result.missing_files == ("docs/missing.md",)
    assert result.files_included == ("docs/stale.md",)
    assert "# Context\nChanged since index." in result.content
    assert (
        "Sections not found in 'docs/stale.md': Decision; included full file as fallback."
        in result.warnings
    )
    assert (
        "File 'docs/stale.md' has been modified since last index; content may be stale. "
        "Re-run indexing to refresh."
    ) in result.warnings


def test_loader_raises_budget_error_in_strict_mode(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "large.md").write_text("# Large\n" + "x " * 100, encoding="utf-8")
    config = _config(
        vault,
        (ContextPackConfig(name="large", paths=("large.md",), token_budget=10),),
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        ContextPackLoader(config).load("large")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET
    assert error.details["current_token_count"] > error.details["budget"]
    assert error.details["excess_tokens"] > 0
    assert "strict_budget=false" in error.details["suggestion"]


def test_loader_reports_unknown_pack_as_invalid_request(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    config = _config(vault, (ContextPackConfig(name="known", paths=("README.md",)),))

    with pytest.raises(ToolExecutionError) as exc_info:
        ContextPackLoader(config).load("missing")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_REQUEST
    assert error.details["known_context_packs"] == ["known"]
    assert error.details["closest_matches"] == []
    assert "list_context_packs" in error.details["suggestion"]


def test_loader_suggests_close_context_pack_names(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    config = _config(
        vault,
        (
            ContextPackConfig(name="overview", paths=("README.md",)),
            ContextPackConfig(name="deep-dive", paths=("README.md",)),
        ),
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        ContextPackLoader(config).load("overveiw")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_REQUEST
    assert error.details["known_context_packs"] == ["deep-dive", "overview"]
    assert error.details["closest_matches"] == ["overview"]


def test_loader_lists_configured_context_pack_metadata(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    config = _config(
        vault,
        (
            ContextPackConfig(
                name="overview",
                description="High-level project docs",
                paths=("docs/*.md",),
            ),
            ContextPackConfig(
                name="api",
                paths=("wiki/api/**/*.md",),
                sections=("authentication",),
                tags_filter=("public",),
                include_context_packs=("overview",),
                token_budget=1200,
            ),
        ),
    )

    summaries = ContextPackLoader(config).list_packs()

    assert len(summaries) == 2
    assert summaries[0].pack_name == "overview"
    assert summaries[0].description == "High-level project docs"
    assert summaries[0].token_budget == 8000
    assert summaries[1].pack_name == "api"
    assert summaries[1].token_budget == 1200
    assert summaries[1].sections == ("authentication",)
    assert summaries[1].tags_filter == ("public",)
    assert summaries[1].include_context_packs == ("overview",)


def _insert_indexed_file(
    config: ProjectConfig,
    vault_path: str,
    *,
    indexed_at: str,
    mtime_ns: int | None = None,
) -> None:
    path = config.vault_path / vault_path
    stat = path.stat()
    stored_mtime_ns = mtime_ns or int(
        datetime(1970, 1, 1, tzinfo=UTC).timestamp() * 1_000_000_000
    )
    ensure_index_migrated(config.index_db_location)
    connection = connect_index_db(config.index_db_location)
    try:
        connection.execute(
            """
            INSERT INTO files (
                vault_path, size_bytes, mtime_ns, parser_version, indexed_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                vault_path,
                stat.st_size,
                stored_mtime_ns,
                PARSER_VERSION,
                indexed_at,
            ),
        )
        connection.commit()
    finally:
        connection.close()
