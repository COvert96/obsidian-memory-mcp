from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.proposals import ProposalManager
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR


def _write_config(vault: Path) -> None:
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
""",
        encoding="utf-8",
    )


def _write_registry(tmp_path: Path, vault: Path) -> Path:
    registry = tmp_path / "memory-mcp-server.yaml"
    registry.write_text(
        f'projects:\n  sample: "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    return registry


def _call(tool: str, arguments: dict) -> dict:
    content_blocks, _structured = cast(
        tuple[list[Any], dict[str, Any]],
        asyncio.run(mcp.call_tool(tool, arguments)),
    )
    return cast(dict[str, Any], json.loads(content_blocks[0].text))


def test_approval_workflow_rejects_hash_conflicts_and_applies_atomic_writes(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / ".mcp").mkdir(parents=True)
    (vault / "Memory").mkdir()
    _write_config(vault)
    target = vault / "Memory" / "note.md"
    target.write_text("# Note\nold", encoding="utf-8")
    manager = ProposalManager(ConfigLoader(vault).load())
    stale = manager.create(
        file_path="Memory/note.md",
        operation="update",
        content="# Note\nnew",
    )
    target.write_text("# Note\nchanged elsewhere", encoding="utf-8")

    with pytest.raises(ToolExecutionError) as conflict:
        manager.approve(stale.proposal_id)

    fresh = manager.create(
        file_path="Memory/note.md",
        operation="update",
        content="# Note\napproved",
    )
    applied = manager.approve(fresh.proposal_id)

    assert conflict.value.error.code is ErrorCode.ERR_STALE_PROPOSAL
    assert target.read_text(encoding="utf-8") == "# Note\napproved"
    assert applied.status == "applied"
    assert applied.file_size_bytes == len("# Note\napproved".encode("utf-8"))
    assert [event.event_type for event in manager.events(stale.proposal_id)] == [
        "created",
        "approval_attempt",
        "apply_rejection",
    ]
    assert [event.event_type for event in manager.events(fresh.proposal_id)] == [
        "created",
        "approval_attempt",
        "applied",
    ]


def test_approval_creates_parent_directories_and_delete_detects_missing_target(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / ".mcp").mkdir(parents=True)
    (vault / "Memory").mkdir()
    _write_config(vault)
    manager = ProposalManager(ConfigLoader(vault).load())

    create = manager.create(
        file_path="Memory/deep/new.md",
        operation="create",
        content="# New nested note",
    )
    manager.approve(create.proposal_id)
    delete_target = vault / "Memory" / "delete-me.md"
    delete_target.write_text("# Delete me", encoding="utf-8")
    stale_delete = manager.create(file_path="Memory/delete-me.md", operation="delete")
    delete_target.unlink()

    with pytest.raises(ToolExecutionError) as missing:
        manager.approve(stale_delete.proposal_id)

    assert (
        vault.joinpath("Memory", "deep", "new.md").read_text(encoding="utf-8")
        == "# New nested note"
    )
    assert missing.value.error.code is ErrorCode.ERR_STALE_PROPOSAL
    assert "no longer exists" in missing.value.error.message


def test_delete_proposal_approval_removes_existing_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".mcp").mkdir(parents=True)
    (vault / "Memory").mkdir()
    _write_config(vault)
    delete_target = vault / "Memory" / "delete-me.md"
    delete_target.write_text("# Delete me", encoding="utf-8")
    manager = ProposalManager(ConfigLoader(vault).load())
    proposal = manager.create(file_path="Memory/delete-me.md", operation="delete")

    result = manager.approve(proposal.proposal_id)

    assert result.status == "applied"
    assert result.file_size_bytes == 0
    assert not delete_target.exists()


def test_mcp_proposal_tools_cover_propose_list_and_approve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = tmp_path / "vault"
    (vault / ".mcp").mkdir(parents=True)
    vault.mkdir(exist_ok=True)
    _write_config(vault)
    registry = _write_registry(tmp_path, vault)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))

    created = _call(
        "propose_memory_update",
        {
            "project": "sample",
            "file_path": "Memory/from-mcp.md",
            "operation": "create",
            "content": "# From MCP",
        },
    )
    listed = _call(
        "list_proposals",
        {"project": "sample", "status": "pending", "file_path": "Memory/from-mcp.md"},
    )
    approved = _call(
        "approve_proposal",
        {"project": "sample", "proposal_id": created["proposal_id"]},
    )

    assert created["old_hash"] is None
    assert created["new_hash"]
    assert created["ttl_seconds"] == 3600
    assert listed["returned_count"] == 1
    assert listed["proposals"][0]["preview"] == "# From MCP"
    assert approved["status"] == "applied"
    assert (
        vault.joinpath("Memory", "from-mcp.md").read_text(encoding="utf-8")
        == "# From MCP"
    )


def test_mcp_reject_proposal_marks_proposal_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = tmp_path / "vault"
    (vault / ".mcp").mkdir(parents=True)
    vault.mkdir(exist_ok=True)
    _write_config(vault)
    registry = _write_registry(tmp_path, vault)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))
    created = _call(
        "propose_memory_update",
        {
            "project": "sample",
            "file_path": "Memory/rejected.md",
            "operation": "create",
            "content": "# Rejected",
        },
    )

    rejected = _call(
        "reject_proposal",
        {"project": "sample", "proposal_id": created["proposal_id"]},
    )
    listed = _call(
        "list_proposals",
        {"project": "sample", "status": "rejected"},
    )

    assert rejected["status"] == "rejected"
    assert listed["returned_count"] == 1
    assert listed["proposals"][0]["proposal_id"] == created["proposal_id"]
    assert not vault.joinpath("Memory", "rejected.md").exists()


def test_mcp_approval_returns_invalid_request_for_missing_proposal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = tmp_path / "vault"
    (vault / ".mcp").mkdir(parents=True)
    vault.mkdir(exist_ok=True)
    _write_config(vault)
    registry = _write_registry(tmp_path, vault)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))

    with pytest.raises(ToolError) as missing:
        _call(
            "approve_proposal",
            {"project": "sample", "proposal_id": "missing"},
        )

    assert ErrorCode.ERR_INVALID_REQUEST.value in str(missing.value)
