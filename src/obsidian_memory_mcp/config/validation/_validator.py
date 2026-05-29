from __future__ import annotations

from pathlib import Path
from typing import Any

from obsidian_memory_mcp.config._models import ProjectConfig
from obsidian_memory_mcp.config.validation._context_packs import validate_context_packs
from obsidian_memory_mcp.config.validation._errors import (
    ConfigValidationError,
    ConfigValidationException,
    validation_error_response,
)
from obsidian_memory_mcp.config.validation._optional_fields import (
    resolve_max_write_content_bytes,
    validate_optional_fields,
    warn_removed_proposal_fields,
)
from obsidian_memory_mcp.config.validation._parsers import (
    parse_context_packs,
    parse_write_constraints,
    resolve_config_path,
)
from obsidian_memory_mcp.config.validation._vault_fields import (
    missing_required_field_errors,
    validate_index_db_location,
    validated_vault_path,
)
from obsidian_memory_mcp.config.validation._write_policy import validate_write_constraints


class ConfigValidator:
    def collect_errors(self, data: Any) -> list[ConfigValidationError]:
        if not isinstance(data, dict):
            return [
                ConfigValidationError(
                    field="config",
                    expected="a YAML object",
                    actual=data,
                    suggestion="Use key/value mappings at the top level of memory-mcp.yaml.",
                )
            ]

        errors: list[ConfigValidationError] = []
        errors.extend(missing_required_field_errors(data))
        vault_path = validated_vault_path(data, errors)
        validate_index_db_location(data, vault_path, errors)
        validate_context_packs(data, errors)
        validate_write_constraints(data, errors)
        validate_optional_fields(data, errors)
        return errors

    def validate(self, data: Any) -> ProjectConfig:
        errors = self.collect_errors(data)
        if errors:
            raise ConfigValidationException(validation_error_response(errors), errors)

        warn_removed_proposal_fields(data)
        vault_path = Path(data["vault_path"]).resolve()
        return ProjectConfig(
            vault_path=vault_path,
            index_db_location=resolve_config_path(
                vault_path, data["index_db_location"]
            ),
            context_packs=parse_context_packs(data["context_packs"]),
            write_constraints=parse_write_constraints(data["write_constraints"]),
            tags_separator=data.get(
                "tags_separator",
                ProjectConfig.DEFAULT_TAGS_SEPARATOR,
            ),
            max_write_content_bytes=resolve_max_write_content_bytes(data),
            memory_archive_path=data.get(
                "memory_archive_path",
                ProjectConfig.DEFAULT_MEMORY_ARCHIVE_PATH,
            ),
        )
