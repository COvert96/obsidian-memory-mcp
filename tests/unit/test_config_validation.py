from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.config import (
    ConfigLoader,
    ConfigValidationException,
    ConfigValidator,
    ProjectConfig,
    load_project_config,
)
from obsidian_memory_mcp.errors import ErrorCode


def valid_config(vault_path: Path) -> dict[str, object]:
    return {
        "vault_path": str(vault_path),
        "index_db_location": "memory-index.sqlite3",
        "context_packs": [
            {
                "name": "prd",
                "paths": ["docs/prd/**/*.md"],
                "include_context_packs": ["foundation"],
            },
            {"name": "foundation", "paths": ["README.md"]},
        ],
        "write_constraints": {
            "read": {"allow": ["**/*.md"], "deny": ["private/**"]},
            "write": {"allow": ["wiki/proposals/"], "deny": ["wiki/log.md"]},
        },
        "tags_separator": ",",
        "max_write_content_bytes": 1048576,
    }


def write_config(vault_path: Path, content: str) -> Path:
    config_path = vault_path / ProjectConfig.CONFIG_FILE_NAME
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_loader_reads_config_from_vault_root_and_caches_it(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_config(
        vault,
        """
vault_path: "{vault}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: prd
    paths:
      - docs/prd/**/*.md
write_constraints:
  read:
    allow:
      - "**/*.md"
  write:
    allow:
      - Memory/**
tags_separator: "|"
""".format(vault=vault.as_posix()),
    )
    loader = ConfigLoader(vault)

    loaded = loader.load()
    write_config(vault, "not: the same config anymore\n")

    assert loaded is loader.load()
    assert loaded.vault_path == vault.resolve()
    assert loaded.index_db_location == vault.resolve() / "memory-index.sqlite3"
    assert loaded.tags_separator == "|"
    assert loaded.max_write_content_bytes == 1024 * 1024
    assert loaded.memory_archive_path == "Memory/archive"


def test_loader_reports_missing_config_with_actionable_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    with pytest.raises(ConfigValidationException) as exc_info:
        ConfigLoader(vault).load()

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_PROJECT
    assert str(vault / ProjectConfig.CONFIG_FILE_NAME) in error.message
    assert "Create memory-mcp.yaml" in error.details["suggestion"]


def test_loader_reports_malformed_yaml(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_config(vault, "vault_path: [unterminated\n")

    with pytest.raises(ConfigValidationException) as exc_info:
        ConfigLoader(vault).load()

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_PROJECT
    assert "malformed YAML" in exc_info.value.error.message


def test_validator_accepts_relative_index_db_location_inside_vault(
    tmp_path: Path,
) -> None:
    config = ConfigValidator().validate(valid_config(tmp_path))

    assert config.index_db_location == tmp_path.resolve() / "memory-index.sqlite3"


def test_validator_collects_missing_required_fields(tmp_path: Path) -> None:
    data = {"vault_path": str(tmp_path)}

    errors = ConfigValidator().collect_errors(data)

    assert {error.field for error in errors} == {
        "index_db_location",
        "context_packs",
        "write_constraints",
    }
    assert all(error.suggestion for error in errors)


def test_validator_reports_wrong_types_with_actual_values(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = "prd"
    data["write_constraints"] = []
    data["tags_separator"] = ["|"]
    data["max_write_content_bytes"] = "large"

    errors = ConfigValidator().collect_errors(data)

    assert {error.field for error in errors} >= {
        "context_packs",
        "write_constraints",
        "tags_separator",
        "max_write_content_bytes",
    }
    assert any("Got 'prd'" in error.message for error in errors)
    assert any("expected type" in error.suggestion for error in errors)


def test_validator_rejects_relative_vault_path(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["vault_path"] = "relative/path"

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "vault_path"
    assert "absolute path" in errors[0].message
    assert "Use '/full/path' instead" in errors[0].suggestion


def test_validator_rejects_missing_vault_directory(tmp_path: Path) -> None:
    data = valid_config(tmp_path / "missing")

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "vault_path"
    assert "existing directory" in errors[0].message


def test_validator_rejects_absolute_index_path_outside_vault(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.sqlite3"
    data = valid_config(tmp_path)
    data["index_db_location"] = str(outside)

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "index_db_location"
    assert "inside vault_path" in errors[0].message


def test_validator_rejects_context_pack_without_name_or_paths(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [{"name": "", "paths": []}, {"paths": ["README.md"]}]

    errors = ConfigValidator().collect_errors(data)

    assert {error.field for error in errors} >= {
        "context_packs[0].name",
        "context_packs[0].paths",
        "context_packs[1].name",
    }


def test_validator_accepts_full_context_pack_schema(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [
        {
            "name": "architecture",
            "description": "Architecture decisions and overview",
            "paths": ["docs/architecture.md"],
            "sections": ["Decision", "Context"],
            "tags_filter": ["architecture", "public"],
            "include_context_packs": ["foundation"],
            "token_budget": 6000,
        },
        {"name": "foundation", "paths": ["README.md"]},
    ]

    config = ConfigValidator().validate(data)
    pack = config.context_packs[0]

    assert pack.description == "Architecture decisions and overview"
    assert pack.sections == ("Decision", "Context")
    assert pack.tags_filter == ("architecture", "public")
    assert pack.token_budget == 6000


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", 123),
        ("sections", "Decision"),
        ("sections", [None]),
        ("tags_filter", "public"),
        ("tags_filter", [123]),
        ("token_budget", 0),
    ],
)
def test_validator_rejects_invalid_context_pack_schema_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [
        {
            "name": "architecture",
            "paths": ["docs/architecture.md"],
            field: value,
        }
    ]

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == f"context_packs[0].{field}"


def test_validator_rejects_duplicate_context_pack_names(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [
        {"name": "prd", "paths": ["docs/**/*.md"]},
        {"name": "prd", "paths": ["README.md"]},
    ]

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "context_packs[1].name"
    assert "unique" in errors[0].message


def test_validator_rejects_unknown_context_pack_references(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [
        {
            "name": "prd",
            "paths": ["docs/**/*.md"],
            "include_context_packs": ["missing"],
        },
    ]

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "context_packs[0].include_context_packs"
    assert "unknown context pack" in errors[0].message


def test_validator_reports_original_index_for_unknown_context_pack_references(
    tmp_path: Path,
) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [
        {"name": "first", "paths": ["first.md"]},
        {"name": "second", "paths": ["second.md"]},
        {"name": "third", "paths": ["third.md"], "include_context_packs": ["missing"]},
    ]

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "context_packs[2].include_context_packs"


def test_validator_rejects_circular_context_pack_references(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["context_packs"] = [
        {"name": "a", "paths": ["a.md"], "include_context_packs": ["b"]},
        {"name": "b", "paths": ["b.md"], "include_context_packs": ["c"]},
        {"name": "c", "paths": ["c.md"], "include_context_packs": ["a"]},
    ]

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == "context_packs"
    assert "circular reference" in errors[0].message


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("write_constraints.read.allow", "wiki/**"),
        ("write_constraints.write.allow", [123]),
        ("write_constraints.write.deny", [None]),
    ],
)
def test_validator_rejects_invalid_constraint_lists(
    tmp_path: Path, field: str, value: object
) -> None:
    data = valid_config(tmp_path)
    constraints = data["write_constraints"]
    assert isinstance(constraints, dict)
    section, list_name = field.split(".")[1:]
    constraints[section][list_name] = value  # type: ignore[index]

    errors = ConfigValidator().collect_errors(data)

    assert errors[0].field == field
    assert "list of strings" in errors[0].message


def test_validator_raises_with_all_errors(tmp_path: Path) -> None:
    data = {"vault_path": "relative/path", "context_packs": "prd"}

    with pytest.raises(ConfigValidationException) as exc_info:
        ConfigValidator().validate(data)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_PROJECT
    assert len(exc_info.value.validation_errors) >= 3
    assert "vault_path" in exc_info.value.error.message


def test_validator_defaults_memory_archive_path_when_absent(tmp_path: Path) -> None:
    config = ConfigValidator().validate(valid_config(tmp_path))

    assert config.memory_archive_path == "Memory/archive"


def test_validator_reads_memory_archive_path_when_present(tmp_path: Path) -> None:
    data = valid_config(tmp_path)
    data["memory_archive_path"] = "Memory/old-notes"

    config = ConfigValidator().validate(data)

    assert config.memory_archive_path == "Memory/old-notes"


@pytest.mark.parametrize(
    "value",
    [
        "/absolute/Memory/archive",
        "archive",
        "wiki/archive",
        "Memory/../escape",
        123,
    ],
)
def test_validator_rejects_invalid_memory_archive_path(
    tmp_path: Path, value: object
) -> None:
    data = valid_config(tmp_path)
    data["memory_archive_path"] = value

    errors = ConfigValidator().collect_errors(data)

    assert any(error.field == "memory_archive_path" for error in errors)


def test_validator_warns_on_removed_proposal_field_without_raising(
    tmp_path: Path,
) -> None:
    data = valid_config(tmp_path)
    data["proposal_ttl_seconds"] = 3600

    with pytest.warns(DeprecationWarning, match="proposal_ttl_seconds"):
        config = ConfigValidator().validate(data)

    assert config.vault_path == tmp_path.resolve()


def test_load_project_config_convenience_function(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
vault_path: "{vault}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: default
    paths: ["README.md"]
write_constraints:
  read:
    allow: ["README.md"]
  write:
    allow: ["wiki/proposals/"]
""".format(vault=tmp_path.as_posix()),
    )

    config = load_project_config(tmp_path)

    assert config.context_packs[0].name == "default"


def test_load_project_config_reuses_cached_loader(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
vault_path: "{vault}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: default
    paths: ["README.md"]
write_constraints:
  read:
    allow: ["README.md"]
  write:
    allow: ["wiki/proposals/"]
""".format(vault=tmp_path.as_posix()),
    )

    first = load_project_config(tmp_path)
    write_config(tmp_path, "not: the same config anymore\n")

    assert load_project_config(tmp_path) is first
