from __future__ import annotations

import time
from pathlib import Path

import pytest

from obsidian_memory_mcp.config import (
    GuardrailEvaluator,
    ProjectConfig,
    WriteConstraints,
    WritePolicy,
)
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError


@pytest.fixture
def config(tmp_path: Path) -> ProjectConfig:
    vault = tmp_path / "vault"
    (vault / "wiki" / "proposals").mkdir(parents=True)
    (vault / "wiki" / "notes").mkdir()
    return ProjectConfig(
        vault_path=vault.resolve(),
        index_db_location=vault.resolve() / "index.sqlite3",
        context_packs=(),
        write_constraints=WriteConstraints(
            read=WritePolicy(allow=("wiki/**", "README.md"), deny=("wiki/private/**",)),
            write=WritePolicy(allow=("wiki/proposals/", "wiki/notes/*.md"), deny=("wiki/log.md",)),
        ),
        tags_separator=",",
        max_proposal_ttl_hours=24,
    )


def test_read_allows_matching_glob(config: ProjectConfig) -> None:
    assert GuardrailEvaluator(config).check_read("wiki/notes/alpha.md") == config.vault_path / "wiki" / "notes" / "alpha.md"


def test_read_rejects_default_denied_path(config: ProjectConfig) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        GuardrailEvaluator(config).check_read("secrets/passwords.md")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION
    assert "read" in exc_info.value.error.message


def test_read_deny_overrides_allow(config: ProjectConfig) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        GuardrailEvaluator(config).check_read("wiki/private/plan.md")

    assert "deny" in exc_info.value.error.message


def test_write_allows_directory_pattern(config: ProjectConfig) -> None:
    result = GuardrailEvaluator(config).check_write("wiki/proposals/new.md")

    assert result == config.vault_path / "wiki" / "proposals" / "new.md"


def test_write_allows_explicit_glob_pattern(config: ProjectConfig) -> None:
    result = GuardrailEvaluator(config).check_write("wiki/notes/new.md")

    assert result == config.vault_path / "wiki" / "notes" / "new.md"


def test_write_rejects_nested_file_when_glob_is_not_recursive(config: ProjectConfig) -> None:
    with pytest.raises(ToolExecutionError):
        GuardrailEvaluator(config).check_write("wiki/notes/deep/new.md")


def test_write_deny_overrides_directory_allow(config: ProjectConfig) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        GuardrailEvaluator(config).check_write("wiki/log.md")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION
    assert "write deny" in exc_info.value.error.message


def test_guardrail_checks_block_traversal_before_pattern_matching(config: ProjectConfig) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        GuardrailEvaluator(config).check_read("../outside.md")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_guardrail_check_completes_under_one_millisecond(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    config = ProjectConfig(
        vault_path=vault.resolve(),
        index_db_location=vault.resolve() / "index.sqlite3",
        context_packs=(),
        write_constraints=WriteConstraints(
            read=WritePolicy(allow=tuple(f"wiki/{index}/**" for index in range(20))),
            write=WritePolicy(allow=tuple(f"wiki/{index}/**" for index in range(20))),
        ),
        tags_separator=",",
        max_proposal_ttl_hours=24,
    )
    evaluator = GuardrailEvaluator(config)

    evaluator.check_read("wiki/19/note.md")
    started = time.perf_counter()
    for _ in range(100):
        evaluator.check_read("wiki/19/note.md")
    elapsed = (time.perf_counter() - started) / 100

    assert elapsed < 0.001
