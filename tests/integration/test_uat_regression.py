"""Regression tests mapped to UAT v0.2.0 failing cases (post-remediation)."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.config import ConfigLoader, GuardrailEvaluator
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.retrieval import ReadNoteService, ReadSectionService
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR

FIXTURE_SOURCE = Path(__file__).parents[1] / "fixtures" / "sample-vault"


def _call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    content_blocks, _structured = cast(
        tuple[list[Any], dict[str, Any]],
        asyncio.run(mcp.call_tool(tool, arguments)),
    )
    return cast(dict[str, Any], json.loads(content_blocks[0].text))


def _call_expect_error(tool: str, arguments: dict[str, Any]) -> ToolError:
    with pytest.raises(ToolError) as exc_info:
        _call(tool, arguments)
    return exc_info.value


@pytest.fixture()
def sample_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vault = tmp_path / "sample-vault"
    shutil.copytree(FIXTURE_SOURCE, vault)
    registry = tmp_path / "memory-mcp-server.yaml"
    registry.write_text(
        f'projects:\n  sample: "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))
    return vault


def test_uat_tc_rs_01_read_section_includes_context_suffix(sample_vault: Path) -> None:
    config = ConfigLoader(sample_vault).load()
    result = ReadSectionService(config, GuardrailEvaluator(config)).read(
        "wiki/concepts/compliance-as-code.md",
        "Evidence Pipeline",
    )

    assert result["heading"] == "Evidence Pipeline"
    assert "context_prefix" in result
    assert "context_suffix" in result
    assert isinstance(result["context_suffix"], str)


def test_uat_tc_rs_02_read_section_case_insensitive_heading(sample_vault: Path) -> None:
    config = ConfigLoader(sample_vault).load()
    service = ReadSectionService(config, GuardrailEvaluator(config))
    mixed = service.read(
        "wiki/concepts/compliance-as-code.md",
        "Evidence Pipeline",
    )
    lower = service.read(
        "wiki/concepts/compliance-as-code.md",
        "evidence pipeline",
    )

    assert mixed["heading"] == lower["heading"]
    assert mixed["context_suffix"] == lower["context_suffix"]


def test_uat_tc_rn_05_empty_note_path_returns_invalid_request(
    sample_vault: Path,
) -> None:
    config = ConfigLoader(sample_vault).load()
    with pytest.raises(ToolExecutionError) as exc_info:
        ReadNoteService(config, GuardrailEvaluator(config)).read("")

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST


def test_uat_tc_wm_03_write_memory_outside_memory_returns_guardrail(
    sample_vault: Path,
) -> None:
    error = _call_expect_error(
        "write_memory",
        {
            "project": "sample",
            "file_path": "wiki/concepts/bad-note.md",
            "content": "Content.",
        },
    )
    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(error)


def test_uat_tc_wn_02_write_note_memory_path_returns_guardrail(
    sample_vault: Path,
) -> None:
    error = _call_expect_error(
        "write_note",
        {
            "project": "sample",
            "file_path": "Memory/wrong-tool.md",
            "content": "Wrong tool.",
        },
    )
    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(error)


def test_uat_tc_un_05_update_note_memory_path_returns_guardrail(
    sample_vault: Path,
) -> None:
    (sample_vault / "Memory" / "uat-test-note.md").write_text("# Note\n", encoding="utf-8")

    error = _call_expect_error(
        "update_note",
        {
            "project": "sample",
            "file_path": "Memory/uat-test-note.md",
            "content": "Wrong tool.",
        },
    )
    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(error)
