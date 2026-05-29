"""Unit tests for SupersessionService.plan()/commit()/archive()."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from obsidian_memory_mcp.config import (
    AccessConstraints,
    AccessPolicy,
    GuardrailEvaluator,
    ProjectConfig,
)
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.writes import _supersession
from obsidian_memory_mcp.writes._supersession import SupersessionService

_WRITTEN_AT = datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC)


def _config(vault: Path) -> ProjectConfig:
    return ProjectConfig(
        vault_path=vault,
        index_db_location=vault / ".mcp" / "memory-index.sqlite3",
        context_packs=(),
        write_constraints=AccessConstraints(
            read=AccessPolicy(allow=("**/*.md",)),
            write=AccessPolicy(allow=("Memory/**",)),
        ),
    )


def _service(vault: Path) -> SupersessionService:
    config = _config(vault)
    return SupersessionService(config, GuardrailEvaluator(config))


def _write_note(vault: Path, relative: str, content: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    end = text.index("\n---", 4)
    return yaml.safe_load(text[4:end])


def test_single_supersession_archives_and_links_both_notes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(
        vault,
        "Memory/old.md",
        "---\ntopic: company\n---\n# Old\nOld truth.",
    )
    new = _write_note(vault, "Memory/new.md", "# New\nNew truth.")

    archived = _service(vault).archive(["Memory/old.md"], "Memory/new.md", _WRITTEN_AT)

    assert archived == ["Memory/archive/old.md"]
    assert not (vault / "Memory" / "old.md").exists()

    archived_text = (vault / "Memory" / "archive" / "old.md").read_text("utf-8")
    archived_fm = _frontmatter(archived_text)
    assert archived_fm["topic"] == "company"
    assert archived_fm["superseded"] is True
    assert archived_fm["superseded_by"] == "Memory/new.md"
    assert archived_fm["superseded_at"] == _WRITTEN_AT.isoformat()
    assert "Old truth." in archived_text

    new_fm = _frontmatter(new.read_text("utf-8"))
    assert new_fm["supersedes"] == ["Memory/archive/old.md"]


def test_multiple_supersessions(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/a.md", "# A")
    _write_note(vault, "Memory/b.md", "# B")
    _write_note(vault, "Memory/new.md", "# New")

    archived = _service(vault).archive(
        ["Memory/a.md", "Memory/b.md"], "Memory/new.md", _WRITTEN_AT
    )

    assert sorted(archived) == ["Memory/archive/a.md", "Memory/archive/b.md"]
    new_fm = _frontmatter((vault / "Memory" / "new.md").read_text("utf-8"))
    assert sorted(new_fm["supersedes"]) == sorted(archived)


def test_name_collision_in_archive_gets_uuid_suffix(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/archive/old.md", "# Pre-existing archive entry")
    _write_note(vault, "Memory/old.md", "# Old")
    _write_note(vault, "Memory/new.md", "# New")

    archived = _service(vault).archive(["Memory/old.md"], "Memory/new.md", _WRITTEN_AT)

    assert archived != ["Memory/archive/old.md"]
    assert len(archived) == 1
    name = Path(archived[0]).name
    assert name.startswith("old-") and name.endswith(".md")
    assert (vault / archived[0]).exists()
    assert (vault / "Memory" / "archive" / "old.md").read_text("utf-8") == (
        "# Pre-existing archive entry"
    )


def test_collision_between_two_planned_destinations(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/x/old.md", "# X old")
    _write_note(vault, "Memory/y/old.md", "# Y old")
    _write_note(vault, "Memory/new.md", "# New")

    archived = _service(vault).archive(
        ["Memory/x/old.md", "Memory/y/old.md"], "Memory/new.md", _WRITTEN_AT
    )

    assert len(set(archived)) == 2
    for path in archived:
        assert (vault / path).exists()


def test_note_without_frontmatter_gets_block_prepended(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/bare.md", "# Bare\nNo frontmatter.")
    _write_note(vault, "Memory/new.md", "# New")

    _service(vault).archive(["Memory/bare.md"], "Memory/new.md", _WRITTEN_AT)

    text = (vault / "Memory" / "archive" / "bare.md").read_text("utf-8")
    fm = _frontmatter(text)
    assert fm["superseded"] is True
    assert "# Bare" in text


def test_self_supersession_is_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/note.md", "# Note")

    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault).plan(["Memory/note.md"], "Memory/note.md")

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST


def test_duplicate_paths_are_deduplicated(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/old.md", "# Old")
    _write_note(vault, "Memory/new.md", "# New")

    plan = _service(vault).plan(["Memory/old.md", "Memory/old.md"], "Memory/new.md")

    assert len(plan.moves) == 1


def test_plan_rejects_non_memory_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "wiki/old.md", "# Old")

    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault).plan(["wiki/old.md"], "Memory/new.md")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_plan_rejects_missing_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)

    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault).plan(["Memory/ghost.md"], "Memory/new.md")

    assert exc_info.value.error.code is ErrorCode.ERR_MISSING_FILE


def test_plan_does_not_touch_disk(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/old.md", "# Old")
    _write_note(vault, "Memory/new.md", "# New")

    _service(vault).plan(["Memory/old.md"], "Memory/new.md")

    assert (vault / "Memory" / "old.md").exists()
    assert not (vault / "Memory" / "archive").exists()


def test_partial_write_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "vault"
    _write_note(vault, "Memory/a.md", "# A")
    _write_note(vault, "Memory/b.md", "# B")
    _write_note(vault, "Memory/new.md", "# New")
    service = _service(vault)
    plan = service.plan(["Memory/a.md", "Memory/b.md"], "Memory/new.md")

    real_move = _supersession.shutil.move
    calls = {"count": 0}

    def flaky_move(src: str, dst: str) -> object:
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("disk full")
        return real_move(src, dst)

    monkeypatch.setattr(_supersession.shutil, "move", flaky_move)

    with pytest.raises(ToolExecutionError) as exc_info:
        service.commit(plan, "Memory/new.md", _WRITTEN_AT)

    assert exc_info.value.error.code is ErrorCode.ERR_INTERNAL
    # The first move was rolled back to its original location.
    assert (vault / "Memory" / "a.md").exists()
    assert (vault / "Memory" / "b.md").exists()
    # The new note's frontmatter was never back-referenced.
    assert "supersedes" not in (vault / "Memory" / "new.md").read_text("utf-8")
