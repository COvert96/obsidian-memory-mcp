from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from obsidian_memory_mcp.changesets import (
    ChangesetManager,
    ChangesetStatus,
    FileMutation,
)
from obsidian_memory_mcp.config import AccessConstraints, AccessPolicy, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.proposals import ProposalManager, ProposalStatus


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


def test_changeset_reviews_and_approves_multiple_file_mutations_as_one_unit(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    vault.joinpath("Memory", "existing.md").write_text("# Existing\nold", encoding="utf-8")
    manager = ChangesetManager(
        _config(vault),
        clock=lambda: datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        id_factory=lambda: "changeset-0001",
        proposal_id_factory=_sequential_ids(),
    )

    created = manager.create(
        title="Publish related memory updates",
        mutations=(
            FileMutation(
                file_path="Memory/existing.md",
                operation="update",
                content="# Existing\nnew",
            ),
            FileMutation(
                file_path="Memory/new.md",
                operation="create",
                content="# New\ncontent",
            ),
        ),
    )
    review = manager.review(created.changeset_id)
    approved = manager.approve(created.changeset_id, actor="test-operator")

    assert created.status is ChangesetStatus.PENDING
    assert [item.file_path for item in review.files] == [
        "Memory/existing.md",
        "Memory/new.md",
    ]
    assert all(file.diff for file in review.files)
    assert "Memory/existing.md" in review.summary
    assert approved.status is ChangesetStatus.APPLIED
    assert approved.applied_proposal_ids == ("proposal-0001", "proposal-0002")
    assert vault.joinpath("Memory", "existing.md").read_text(encoding="utf-8") == (
        "# Existing\nnew"
    )
    assert vault.joinpath("Memory", "new.md").read_text(encoding="utf-8") == (
        "# New\ncontent"
    )
    assert {
        proposal.status
        for proposal in manager.proposals(created.changeset_id)
    } == {ProposalStatus.APPLIED}
    assert any(
        event.event_type == "changeset_applied"
        and event.details["actor"] == "test-operator"
        for event in manager.audit(changeset_id=created.changeset_id)
    )


def test_changeset_approval_rejects_file_state_conflicts_without_partial_writes(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    first = vault / "Memory" / "first.md"
    second = vault / "Memory" / "second.md"
    first.write_text("# First\nold", encoding="utf-8")
    second.write_text("# Second\nold", encoding="utf-8")
    manager = ChangesetManager(
        _config(vault),
        id_factory=lambda: "changeset-stale",
        proposal_id_factory=_sequential_ids(),
    )
    created = manager.create(
        title="Coordinated update",
        mutations=(
            FileMutation("Memory/first.md", "update", "# First\nnew"),
            FileMutation("Memory/second.md", "update", "# Second\nnew"),
        ),
    )
    second.write_text("# Second\nchanged elsewhere", encoding="utf-8")

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.approve(created.changeset_id)

    assert exc_info.value.error.code is ErrorCode.ERR_STALE_PROPOSAL
    assert "file-state conflict" in exc_info.value.error.message
    assert first.read_text(encoding="utf-8") == "# First\nold"
    assert second.read_text(encoding="utf-8") == "# Second\nchanged elsewhere"
    stored = manager.get(created.changeset_id)

    assert stored is not None
    assert stored.status is ChangesetStatus.PENDING
    assert {
        proposal.status for proposal in manager.proposals(created.changeset_id)
    } == {ProposalStatus.PENDING}


def test_changeset_cleanup_removes_terminal_changesets_and_member_proposals(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    old_manager = ChangesetManager(
        _config(vault),
        clock=lambda: datetime(2000, 1, 1, tzinfo=UTC),
        id_factory=lambda: "changeset-old",
        proposal_id_factory=_sequential_ids(),
    )
    created = old_manager.create(
        title="Old rejected changeset",
        mutations=(
            FileMutation("Memory/old-a.md", "create", "# Old A"),
            FileMutation("Memory/old-b.md", "create", "# Old B"),
        ),
    )
    old_manager.reject(created.changeset_id, reason="obsolete")
    proposal_ids = tuple(
        proposal.proposal_id for proposal in old_manager.proposals(created.changeset_id)
    )

    cleanup_manager = ChangesetManager(
        _config(vault),
        clock=lambda: datetime(2026, 5, 28, tzinfo=UTC),
    )
    result = cleanup_manager.cleanup(retention_days=7)

    assert result.removed_changesets == 1
    assert result.removed_proposals == 2
    assert cleanup_manager.get(created.changeset_id) is None
    proposal_manager = ProposalManager(_config(vault))
    assert all(proposal_manager.get(proposal_id) is None for proposal_id in proposal_ids)


def test_changeset_reject_marks_changeset_and_member_proposals_rejected(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    manager = ChangesetManager(_config(vault))
    created = manager.create(
        title="Two-file update",
        mutations=(
            FileMutation("Memory/a.md", "create", "# A"),
            FileMutation("Memory/b.md", "create", "# B"),
        ),
    )

    result = manager.reject(
        created.changeset_id,
        reason="not needed",
        notes="rejected during acceptance testing",
    )

    assert result.status is ChangesetStatus.REJECTED
    assert result.reason == "not needed"
    assert result.notes == "rejected during acceptance testing"
    stored = manager.get(created.changeset_id)
    assert stored is not None
    assert stored.status is ChangesetStatus.REJECTED
    assert all(
        proposal.status.value == "rejected"
        for proposal in manager.proposals(created.changeset_id)
    )
    assert not vault.joinpath("Memory", "a.md").exists()
    assert not vault.joinpath("Memory", "b.md").exists()


def test_changeset_requires_at_least_two_mutations(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    manager = ChangesetManager(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.create(
            title="Single mutation — should be rejected",
            mutations=(FileMutation("Memory/only.md", "create", "# Only"),),
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "at least two" in exc_info.value.error.message


def test_changeset_approve_raises_for_already_applied_changeset(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    manager = ChangesetManager(_config(vault))
    created = manager.create(
        title="Two creates",
        mutations=(
            FileMutation("Memory/x.md", "create", "# X"),
            FileMutation("Memory/y.md", "create", "# Y"),
        ),
    )
    manager.approve(created.changeset_id)

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.approve(created.changeset_id)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "applied" in exc_info.value.error.message


def test_changeset_approve_raises_for_already_rejected_changeset(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    manager = ChangesetManager(_config(vault))
    created = manager.create(
        title="Two creates",
        mutations=(
            FileMutation("Memory/p.md", "create", "# P"),
            FileMutation("Memory/q.md", "create", "# Q"),
        ),
    )
    manager.reject(created.changeset_id)

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.approve(created.changeset_id)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "rejected" in exc_info.value.error.message


def test_changeset_reject_raises_for_already_applied_changeset(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    manager = ChangesetManager(_config(vault))
    created = manager.create(
        title="Two creates",
        mutations=(
            FileMutation("Memory/m.md", "create", "# M"),
            FileMutation("Memory/n.md", "create", "# N"),
        ),
    )
    manager.approve(created.changeset_id)

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.reject(created.changeset_id)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "applied" in exc_info.value.error.message


def test_changeset_approve_raises_for_nonexistent_changeset_id(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    manager = ChangesetManager(_config(vault))

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.approve("changeset-does-not-exist")

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "does not exist" in exc_info.value.error.message


def _sequential_ids():
    count = 0

    def next_id() -> str:
        nonlocal count
        count += 1
        return f"proposal-{count:04d}"

    return next_id
