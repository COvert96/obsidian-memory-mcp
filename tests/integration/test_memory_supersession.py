from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from obsidian_memory_mcp.config import AccessConstraints, AccessPolicy, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.memory_workflows import MemorySupersessionWorkflow


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


def test_memory_supersession_preserves_prior_note_and_links_active_successor(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    prior = vault / "Memory" / "company-summary.md"
    prior.write_text(
        "---\ntopic: company\n---\n# Company Summary\nOld source of truth.",
        encoding="utf-8",
    )
    workflow = MemorySupersessionWorkflow(
        _config(vault),
        clock=lambda: datetime(2026, 5, 28, 9, 30, tzinfo=UTC),
        changeset_id_factory=lambda: "changeset-memory",
        proposal_id_factory=_sequential_ids(),
    )

    proposed = workflow.propose_supersession(
        superseded_file_path="Memory/company-summary.md",
        new_file_path="Memory/company-summary-v2.md",
        new_content="# Company Summary\nNew source of truth.",
    )
    review = workflow.review(proposed.changeset_id)
    workflow.approve(proposed.changeset_id, actor="memory-operator")

    old_text = prior.read_text(encoding="utf-8")
    new_text = vault.joinpath("Memory", "company-summary-v2.md").read_text(
        encoding="utf-8"
    )

    assert [file.file_path for file in review.files] == [
        "Memory/company-summary.md",
        "Memory/company-summary-v2.md",
    ]
    assert "status: superseded" in old_text
    assert "superseded_by: Memory/company-summary-v2.md" in old_text
    assert "archived_at: '2026-05-28T09:30:00+00:00'" in old_text
    assert "Old source of truth." in old_text
    assert "status: active" in new_text
    assert "supersedes:" in new_text
    assert "  - Memory/company-summary.md" in new_text
    assert "New source of truth." in new_text


def test_memory_supersession_reports_semantic_contradictions_separately(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    workflow = MemorySupersessionWorkflow(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        workflow.propose_supersession(
            superseded_file_path="Memory/same.md",
            new_file_path="Memory/same.md",
            new_content="# Same",
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "semantic contradiction" in exc_info.value.error.message
    assert "file-state" not in exc_info.value.error.message


def test_memory_supersession_rejects_nested_frontmatter_metadata(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    vault.joinpath("Memory", "prior.md").write_text("# Prior", encoding="utf-8")
    workflow = MemorySupersessionWorkflow(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        workflow.propose_supersession(
            superseded_file_path="Memory/prior.md",
            new_file_path="Memory/new.md",
            new_content=(
                "---\nmetadata:\n  nested: value\n---\n# New source of truth."
            ),
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "frontmatter" in exc_info.value.error.message


def test_memory_supersession_rejects_non_memory_path_for_old_file(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    workflow = MemorySupersessionWorkflow(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        workflow.propose_supersession(
            superseded_file_path="wiki/old-note.md",
            new_file_path="Memory/new-note.md",
            new_content="# New",
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "Memory/" in exc_info.value.error.message


def test_memory_supersession_rejects_non_memory_path_for_new_file(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    vault.joinpath("Memory", "old.md").write_text("# Old", encoding="utf-8")
    workflow = MemorySupersessionWorkflow(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        workflow.propose_supersession(
            superseded_file_path="Memory/old.md",
            new_file_path="wiki/new-note.md",
            new_content="# New",
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "Memory/" in exc_info.value.error.message


def test_memory_supersession_raises_when_superseded_file_does_not_exist(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    workflow = MemorySupersessionWorkflow(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        workflow.propose_supersession(
            superseded_file_path="Memory/does-not-exist.md",
            new_file_path="Memory/successor.md",
            new_content="# Successor",
        )

    assert exc_info.value.error.code is ErrorCode.ERR_MISSING_FILE


def test_memory_supersession_raises_when_successor_file_already_exists(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    vault.joinpath("Memory", "prior.md").write_text("# Prior", encoding="utf-8")
    vault.joinpath("Memory", "successor.md").write_text(
        "# Successor already here", encoding="utf-8"
    )
    workflow = MemorySupersessionWorkflow(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        workflow.propose_supersession(
            superseded_file_path="Memory/prior.md",
            new_file_path="Memory/successor.md",
            new_content="# Successor new content",
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "already exists" in exc_info.value.error.message


def test_memory_supersession_merges_frontmatter_into_note_without_existing_frontmatter(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    prior = vault / "Memory" / "bare.md"
    prior.write_text("# Bare Note\nNo frontmatter here.", encoding="utf-8")
    workflow = MemorySupersessionWorkflow(_config(vault))

    proposed = workflow.propose_supersession(
        superseded_file_path="Memory/bare.md",
        new_file_path="Memory/bare-v2.md",
        new_content="# Bare Note v2\nUpdated content.",
    )
    workflow.approve(proposed.changeset_id)

    old_text = prior.read_text(encoding="utf-8")
    new_text = vault.joinpath("Memory", "bare-v2.md").read_text(encoding="utf-8")

    assert "status: superseded" in old_text
    assert "superseded_by: Memory/bare-v2.md" in old_text
    assert "# Bare Note" in old_text
    assert "status: active" in new_text
    assert "supersedes:" in new_text
    assert "# Bare Note v2" in new_text


def _sequential_ids():
    count = 0

    def next_id() -> str:
        nonlocal count
        count += 1
        return f"proposal-{count:04d}"

    return next_id
