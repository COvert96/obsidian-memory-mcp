from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.errors import ErrorCode
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR


FIXTURE_SOURCE = Path(__file__).parents[1] / "fixtures" / "sample-vault"


def _call(tool: str, arguments: dict) -> dict:
    content_blocks, _structured = asyncio.run(mcp.call_tool(tool, arguments))
    return json.loads(content_blocks[0].text)


def _prepare_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "sample-vault"
    shutil.copytree(FIXTURE_SOURCE, vault)
    (vault / ".mcp").mkdir()
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
    return vault


def _write_registry(tmp_path: Path, vault: Path) -> Path:
    registry = tmp_path / "memory-mcp-server.yaml"
    registry.write_text(
        f'projects:\n  sample: "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    return registry


def _headings(markdown: str) -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in markdown.splitlines()
        if line.startswith("#")
    ]


def test_retrieval_tools_cover_fixture_vault_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = _prepare_vault(tmp_path)
    registry = _write_registry(tmp_path, vault)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))
    config = ConfigLoader(vault).load()
    run_index(config, mode=IndexMode.FULL)

    note_paths = sorted(
        path.relative_to(vault).as_posix()
        for path in vault.rglob("*.md")
        if "memory-mcp.yaml" not in path.parts
    )
    for note_path in note_paths:
        payload = _call("read_note", {"project": "sample", "note_path": note_path})
        raw = vault.joinpath(note_path).read_text(encoding="utf-8")
        assert payload["file_path"] == note_path
        assert payload["content"] == raw
        assert payload["file_size_bytes"] == len(raw.encode("utf-8"))

        for heading in _headings(raw):
            section = _call(
                "read_section",
                {
                    "project": "sample",
                    "note_path": note_path,
                    "heading_name": heading.lower(),
                },
            )
            assert section["file_path"] == note_path
            assert section["heading"].lower() == heading.lower()
            assert section["content"].splitlines()[0].lstrip("#").strip() == heading

    cases = [
        ("compliance", {}, "wiki/concepts/compliance-as-code.md"),
        ("evidence", {}, "wiki/concepts/compliance-as-code.md"),
        ("retrieval", {}, "wiki/api/retrieval-tools.md"),
        ("read note", {}, "wiki/api/retrieval-tools.md"),
        ("read section", {}, "wiki/api/retrieval-tools.md"),
        ('"compliance evidence"', {}, "wiki/concepts/compliance-as-code.md"),
        ("continuous compliance", {}, "wiki/concepts/compliance-as-code.md"),
        ("path filters", {}, "wiki/api/retrieval-tools.md"),
        ("special filenames", {}, "wiki/special/Name With Spaces & Symbols (v1).md"),
        ("archive", {}, "archive/legacy-controls.md"),
        ("migration history", {}, "archive/legacy-controls.md"),
        ("policy files", {}, "wiki/concepts/compliance-as-code.md"),
        ("BM25 ranking", {}, "wiki/api/retrieval-tools.md"),
        (r"/compliance\s+evidence/", {}, "wiki/concepts/compliance-as-code.md"),
        (
            "compliance",
            {"tags": ["urgent", "#api"]},
            "wiki/concepts/compliance-as-code.md",
        ),
        ("retrieval", {"paths": ["wiki/api/**"]}, "wiki/api/retrieval-tools.md"),
    ]
    for query, options, expected_path in cases:
        started = time.perf_counter()
        payload = _call(
            "search_notes",
            {"project": "sample", "query": query, "limit": 5, **options},
        )
        duration_ms = (time.perf_counter() - started) * 1000
        assert duration_ms < 100
        assert payload["results"], query
        assert payload["results"][0]["file_path"] == expected_path, query
        assert payload["results"][0]["heading_level"] >= 1

    excluded = _call(
        "search_notes",
        {
            "project": "sample",
            "query": "private audit",
            "limit": 5,
            "exclude_paths": ["wiki/private/**"],
        },
    )
    assert all(
        item["file_path"] != "wiki/private/secret-compliance.md"
        for item in excluded["results"]
    )


def test_retrieval_tools_surface_expected_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = _prepare_vault(tmp_path)
    registry = _write_registry(tmp_path, vault)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))
    config = ConfigLoader(vault).load()
    run_index(config, mode=IndexMode.FULL)

    with pytest.raises(ToolError) as missing_file:
        _call(
            "read_note",
            {"project": "sample", "note_path": "wiki/missing.md"},
        )
    with pytest.raises(ToolError) as bad_path:
        _call("read_note", {"project": "sample", "note_path": "../escape.md"})
    with pytest.raises(ToolError) as missing_section:
        _call(
            "read_section",
            {
                "project": "sample",
                "note_path": "wiki/api/retrieval-tools.md",
                "heading_name": "Missing",
            },
        )
    with pytest.raises(ToolError) as empty_query:
        _call("search_notes", {"project": "sample", "query": ""})

    assert ErrorCode.ERR_MISSING_FILE.value in str(missing_file.value)
    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(bad_path.value)
    assert ErrorCode.ERR_SECTION_NOT_FOUND.value in str(missing_section.value)
    assert "query is required" in str(empty_query.value)
