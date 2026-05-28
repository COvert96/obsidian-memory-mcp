from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader, GuardrailEvaluator
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.retrieval import ReadNoteService


def _service(vault: Path) -> ReadNoteService:
    config = ConfigLoader(vault).load()
    return ReadNoteService(config, GuardrailEvaluator(config))


def test_read_note_returns_exact_content_frontmatter_size_and_special_path(
    vault_root: Path,
) -> None:
    note = vault_root / "wiki" / "Name With Spaces & Symbols (v1).md"
    content = "---\ntype: concept\ntags: [api]\n---\n# Special\nExact body.\n"
    note.write_text(content, encoding="utf-8")

    result = _service(vault_root).read("wiki/Name With Spaces & Symbols (v1).md")

    assert result == {
        "file_path": "wiki/Name With Spaces & Symbols (v1).md",
        "content": content,
        "frontmatter": {"type": "concept", "tags": ["api"]},
        "file_size_bytes": len(content.encode("utf-8")),
        "content_hash": hashlib.sha256(note.read_bytes()).hexdigest(),
    }


def test_read_note_content_hash_is_raw_byte_hash_for_crlf_file(
    vault_root: Path,
) -> None:
    """The hash is over raw bytes, so CRLF files differ from their LF text."""
    note = vault_root / "wiki" / "crlf.md"
    raw_bytes = b"# Title\r\nLine one.\r\n"
    note.write_bytes(raw_bytes)

    result = _service(vault_root).read("wiki/crlf.md")

    assert isinstance(result["content_hash"], str)
    assert len(result["content_hash"]) == 64
    assert result["content_hash"] == hashlib.sha256(raw_bytes).hexdigest()
    # read_text normalizes CRLF -> LF, so hashing the decoded text would NOT match.
    assert (
        result["content_hash"]
        != hashlib.sha256(str(result["content"]).encode("utf-8")).hexdigest()
    )


def test_read_note_raises_missing_file(vault_root: Path) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault_root).read("wiki/missing.md")

    assert exc_info.value.error.code is ErrorCode.ERR_MISSING_FILE


def test_read_note_raises_guardrail_violation_for_disallowed_path(
    vault_root: Path,
) -> None:
    (vault_root / "secret.txt").write_text("hidden", encoding="utf-8")

    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault_root).read("secret.txt")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_read_note_permission_error_uses_vault_relative_path(
    vault_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    note = vault_root / "wiki" / "locked.md"
    note.write_text("# Locked\n", encoding="utf-8")
    service = _service(vault_root)
    original_read_text = Path.read_text

    def deny_locked(path: Path, *args: object, **kwargs: object) -> str:
        if path == note:
            raise PermissionError("locked")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny_locked)

    with pytest.raises(ToolExecutionError) as exc_info:
        service.read("wiki/locked.md")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION
    assert "wiki/locked.md" in exc_info.value.error.message
    assert str(vault_root) not in exc_info.value.error.message


def test_read_note_reads_100kb_file_under_50ms(vault_root: Path) -> None:
    note = vault_root / "wiki" / "large.md"
    note.write_text("# Large\n" + ("content block\n" * 8000), encoding="utf-8")
    service = _service(vault_root)

    started = time.perf_counter()
    result = service.read("wiki/large.md")
    duration_ms = (time.perf_counter() - started) * 1000

    assert result["file_size_bytes"] > 100_000
    assert duration_ms < 50
