from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from obsidian_memory_mcp.cli import main
from obsidian_memory_mcp.changesets import ChangesetManager, FileMutation
from obsidian_memory_mcp.config import AccessConstraints, AccessPolicy, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.proposals import (
    ProposalManager,
    ProposalOperation,
    ProposalStatus,
)
from obsidian_memory_mcp.proposals.repository import ProposalRepository
from obsidian_memory_mcp.schema import bootstrap_schema, connect_index_db


class FrozenClock:
    def __init__(self, current: datetime):
        self.current = current

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


def _config(
    vault: Path,
    *,
    ttl_seconds: int = 3600,
    max_ttl_hours: int = 24,
    max_content_bytes: int = 1024 * 1024,
) -> ProjectConfig:
    return ProjectConfig(
        vault_path=vault,
        index_db_location=vault / ".mcp" / "memory-index.sqlite3",
        context_packs=(),
        write_constraints=AccessConstraints(
            read=AccessPolicy(allow=("**/*.md",)),
            write=AccessPolicy(allow=("Memory/**",)),
        ),
        max_proposal_ttl_hours=max_ttl_hours,
        proposal_ttl_seconds=ttl_seconds,
        max_proposal_content_bytes=max_content_bytes,
    )


def _write_config(vault: Path, *, ttl_seconds: int = 3600) -> None:
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
proposal_ttl_seconds: {ttl_seconds}
""",
        encoding="utf-8",
    )


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_create_update_and_delete_proposals_capture_hashes_without_writing(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    existing = vault / "Memory" / "existing.md"
    delete_me = vault / "Memory" / "delete-me.md"
    existing.write_bytes(b"# Existing\nold")
    delete_me.write_bytes(b"# Delete\nold")
    manager = ProposalManager(_config(vault), id_factory=_sequential_ids())

    created = manager.create(
        file_path="Memory/new.md",
        operation=ProposalOperation.CREATE,
        content="# New\ncontent",
    )
    updated = manager.create(
        file_path="Memory/existing.md",
        operation=ProposalOperation.UPDATE,
        content="# Existing\nnew",
    )
    deleted = manager.create(
        file_path="Memory/delete-me.md",
        operation=ProposalOperation.DELETE,
    )

    assert not vault.joinpath("Memory", "new.md").exists()
    assert created.old_hash is None
    assert created.new_hash == _sha256("# New\ncontent")
    assert created.ttl_seconds == 3600
    assert updated.old_hash == _sha256("# Existing\nold")
    assert updated.new_hash == _sha256("# Existing\nnew")
    assert deleted.old_hash == _sha256("# Delete\nold")
    assert deleted.new_hash is None


def test_create_and_approve_escape_wikilink_alias_separator_before_write(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    manager = ProposalManager(_config(vault), id_factory=_sequential_ids())
    proposal = manager.create(
        file_path="Memory/table.md",
        operation=ProposalOperation.CREATE,
        content="| Link |\n| --- |\n| [[World/Reference/Helious|Helious]] |",
    )

    stored = manager.get(proposal.proposal_id)
    expected_content = "| Link |\n| --- |\n| [[World/Reference/Helious\\|Helious]] |"

    assert stored is not None
    assert stored.content == expected_content
    assert proposal.new_hash == _sha256(expected_content)

    manager.approve(proposal.proposal_id)

    assert (
        vault.joinpath("Memory", "table.md").read_text(encoding="utf-8")
        == expected_content
    )


def test_proposal_creation_validates_operation_content_and_guardrails(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    manager = ProposalManager(_config(vault))

    with pytest.raises(ToolExecutionError) as missing_content:
        manager.create(
            file_path="Memory/new.md",
            operation=ProposalOperation.CREATE,
        )
    with pytest.raises(ToolExecutionError) as delete_content:
        manager.create(
            file_path="Memory/new.md",
            operation=ProposalOperation.DELETE,
            content="not allowed",
        )
    with pytest.raises(ToolExecutionError) as guardrail:
        manager.create(
            file_path="wiki/new.md",
            operation=ProposalOperation.CREATE,
            content="# Not allowed",
        )

    assert missing_content.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert delete_content.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert guardrail.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_proposal_creation_rejects_existing_create_and_missing_update_delete_targets(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    vault.joinpath("Memory", "existing.md").write_text("already here", encoding="utf-8")
    manager = ProposalManager(_config(vault))

    with pytest.raises(ToolExecutionError) as existing_create:
        manager.create(
            file_path="Memory/existing.md",
            operation=ProposalOperation.CREATE,
            content="replacement",
        )
    with pytest.raises(ToolExecutionError) as missing_update:
        manager.create(
            file_path="Memory/missing.md",
            operation=ProposalOperation.UPDATE,
            content="replacement",
        )
    with pytest.raises(ToolExecutionError) as missing_delete:
        manager.create(
            file_path="Memory/missing.md",
            operation=ProposalOperation.DELETE,
        )

    assert existing_create.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert missing_update.value.error.code is ErrorCode.ERR_MISSING_FILE
    assert missing_delete.value.error.code is ErrorCode.ERR_MISSING_FILE


def test_proposal_ttl_is_clamped_by_project_maximum(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    manager = ProposalManager(_config(vault, ttl_seconds=7200, max_ttl_hours=1))

    proposal = manager.create(
        file_path="Memory/clamped.md",
        operation=ProposalOperation.CREATE,
        content="clamped",
    )

    assert proposal.ttl_seconds == 3600


def test_create_and_update_proposals_reject_oversized_content(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    manager = ProposalManager(_config(vault, max_content_bytes=4))

    with pytest.raises(ToolExecutionError) as exc_info:
        manager.create(
            file_path="Memory/large.md",
            operation=ProposalOperation.CREATE,
            content="12345",
        )

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "exceeds" in exc_info.value.error.message


def test_list_proposals_filters_sorts_newest_first_and_expires_pending_items(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    clock = FrozenClock(datetime(2026, 5, 27, 12, 0, tzinfo=UTC))
    manager = ProposalManager(
        _config(vault, ttl_seconds=2),
        clock=clock.now,
        id_factory=_sequential_ids(),
    )
    first = manager.create(
        file_path="Memory/first.md",
        operation="create",
        content="# First\npreview body",
    )
    clock.advance(1)
    second = manager.create(
        file_path="Memory/second.md",
        operation="create",
        content="# Second\npreview body",
    )

    pending = manager.list(status=ProposalStatus.PENDING)
    by_file = manager.list(file_path="Memory/first.md")
    clock.advance(2)
    expired_pending = manager.list(status=ProposalStatus.PENDING)
    expired = manager.list(status=ProposalStatus.EXPIRED)

    assert [proposal.proposal_id for proposal in pending] == [
        second.proposal_id,
        first.proposal_id,
    ]
    assert by_file[0].proposal_id == first.proposal_id
    assert pending[0].preview == "# Second\npreview body"
    assert expired_pending == ()
    assert {proposal.status for proposal in expired} == {ProposalStatus.EXPIRED}
    assert any(
        event.event_type == "expired" for event in manager.events(first.proposal_id)
    )


def test_list_response_uses_proposal_id_and_preview_truncates_at_word_boundary(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    manager = ProposalManager(_config(vault), id_factory=_sequential_ids())
    manager.create(
        file_path="Memory/long.md",
        operation=ProposalOperation.CREATE,
        content=f"{'alpha ' * 83}splitword tail",
    )

    response = manager.list()[0].as_response()
    preview = response["preview"]

    assert "proposal_id" in response
    assert "id" not in response
    assert isinstance(preview, str)
    assert preview.endswith("...")
    assert not preview.endswith("split...")


def test_reject_marks_pending_proposal_without_applying_it(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    manager = ProposalManager(_config(vault), id_factory=_sequential_ids())
    proposal = manager.create(
        file_path="Memory/rejected.md",
        operation="create",
        content="# Rejected",
    )

    result = manager.reject(proposal.proposal_id)

    assert result.status is ProposalStatus.REJECTED
    assert not vault.joinpath("Memory", "rejected.md").exists()
    assert [item.proposal_id for item in manager.list(status="rejected")] == [
        proposal.proposal_id
    ]
    assert any(
        event.event_type == "rejected" for event in manager.events(proposal.proposal_id)
    )


def test_repository_status_transitions_only_apply_to_pending_proposals(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    clock = FrozenClock(datetime(2026, 5, 27, 12, 0, tzinfo=UTC))
    manager = ProposalManager(
        _config(vault),
        clock=clock.now,
        id_factory=_sequential_ids(),
    )
    proposal = manager.create(
        file_path="Memory/transition.md",
        operation=ProposalOperation.CREATE,
        content="transition",
    )

    connection = connect_index_db(_config(vault).index_db_location)
    try:
        bootstrap_schema(connection)
        repository = ProposalRepository(connection)

        first = repository.mark_applied_if_pending(proposal.proposal_id, clock.now())
        second = repository.mark_rejected_if_pending(proposal.proposal_id, clock.now())
        stored = repository.fetch_by_id(proposal.proposal_id)
    finally:
        connection.close()

    assert first is True
    assert second is False
    assert stored is not None
    assert stored.status is ProposalStatus.APPLIED


def test_cli_lists_approves_and_rejects_proposals_with_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    manager = ProposalManager(_config(vault), id_factory=_sequential_ids())
    approve = manager.create(
        file_path="Memory/cli-approved.md",
        operation="create",
        content="# Approved from CLI",
    )
    reject = manager.create(
        file_path="Memory/cli-rejected.md",
        operation="create",
        content="# Rejected from CLI",
    )
    monkeypatch.chdir(vault)

    list_exit = main(["proposals", "list"])
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    cancelled_exit = main(["proposals", "approve", approve.proposal_id])
    monkeypatch.setattr("builtins.input", lambda _prompt: "YES")
    approved_exit = main(["proposals", "approve", approve.proposal_id])
    rejected_exit = main(["proposals", "reject", reject.proposal_id])
    output = capsys.readouterr().out

    assert list_exit == 0
    assert cancelled_exit == 1
    assert approved_exit == 0
    assert rejected_exit == 0
    assert approve.proposal_id in output
    assert "Memory/cli-approved.md" in output
    assert "create" in output
    assert "pending" in output
    assert "# Approved from CLI" in output
    assert "cancelled" in output.lower()
    assert (
        vault.joinpath("Memory", "cli-approved.md").read_text(encoding="utf-8")
        == "# Approved from CLI"
    )
    assert not vault.joinpath("Memory", "cli-rejected.md").exists()


def test_cli_shows_diff_records_rejection_notes_and_cleans_up_by_retention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    manager = ProposalManager(_config(vault), id_factory=_sequential_ids())
    rejected = manager.create(
        file_path="Memory/reject-with-notes.md",
        operation="create",
        content="# Reject\ncandidate",
    )
    old_clock = FrozenClock(datetime(2000, 1, 1, tzinfo=UTC))
    old_manager = ProposalManager(
        _config(vault),
        clock=old_clock.now,
        id_factory=lambda: "proposal-old",
    )
    old = old_manager.create(
        file_path="Memory/old-rejected.md",
        operation="create",
        content="# Old",
    )
    old_manager.reject(old.proposal_id, reason="duplicate", notes="aged out")
    monkeypatch.chdir(vault)

    show_exit = main(["proposals", "show", rejected.proposal_id, "--diff"])
    rejected_exit = main(
        [
            "proposals",
            "reject",
            rejected.proposal_id,
            "--reason",
            "duplicate",
            "--notes",
            "Replaced by Memory/current.md",
        ]
    )
    audit_exit = main(["proposals", "audit", "--proposal-id", rejected.proposal_id])
    cleanup_exit = main(["proposals", "cleanup", "--yes", "--retention-days", "7"])
    output = capsys.readouterr().out

    assert show_exit == 0
    assert rejected_exit == 0
    assert audit_exit == 0
    assert cleanup_exit == 0
    assert "Diff:" in output
    assert "+# Reject" in output
    assert "duplicate" in output
    assert "Replaced by Memory/current.md" in output
    assert "removed 1 retained proposal" in output
    assert ProposalManager(_config(vault)).get(old.proposal_id) is None


def test_cli_approves_and_rejects_changesets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    _write_config(vault)
    create_manager = ChangesetManager(
        _config(vault),
        id_factory=lambda: "changeset-approve",
        proposal_id_factory=_sequential_ids(),
    )
    approve_changeset = create_manager.create(
        title="Apply grouped create",
        mutations=(
            FileMutation("Memory/a.md", "create", "# A"),
            FileMutation("Memory/b.md", "create", "# B"),
        ),
    )
    reject_changeset = ChangesetManager(
        _config(vault),
        id_factory=lambda: "changeset-reject",
        proposal_id_factory=_prefixed_ids("reject"),
    ).create(
        title="Reject grouped create",
        mutations=(
            FileMutation("Memory/c.md", "create", "# C"),
            FileMutation("Memory/d.md", "create", "# D"),
        ),
    )
    monkeypatch.chdir(vault)
    monkeypatch.setattr("builtins.input", lambda _prompt: "YES")

    approved_exit = main(["proposals", "approve", approve_changeset.changeset_id])
    rejected_exit = main(
        [
            "proposals",
            "reject",
            reject_changeset.changeset_id,
            "--reason",
            "duplicate",
        ]
    )
    output = capsys.readouterr().out

    assert approved_exit == 0
    assert rejected_exit == 0
    assert "Applied changeset changeset-approve" in output
    assert "Rejected changeset changeset-reject" in output
    assert vault.joinpath("Memory", "a.md").read_text(encoding="utf-8") == "# A"
    assert not vault.joinpath("Memory", "c.md").exists()


def _sequential_ids():
    count = 0

    def next_id() -> str:
        nonlocal count
        count += 1
        return f"proposal-{count:04d}"

    return next_id


def _prefixed_ids(prefix: str):
    count = 0

    def next_id() -> str:
        nonlocal count
        count += 1
        return f"{prefix}-{count:04d}"

    return next_id
