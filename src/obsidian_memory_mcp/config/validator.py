from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from obsidian_memory_mcp.config.model import (
    DEFAULT_MAX_PROPOSAL_TTL_HOURS,
    DEFAULT_TAGS_SEPARATOR,
    AccessConstraints,
    AccessPolicy,
    ContextPackConfig,
    ProjectConfig,
)
from obsidian_memory_mcp.errors import (
    ErrorCode,
    ErrorResponse,
    ToolExecutionError,
    build_error,
)


@dataclass(frozen=True)
class ConfigValidationError:
    field: str
    expected: str
    actual: Any
    suggestion: str

    @property
    def message(self) -> str:
        return (
            f"Field '{self.field}' must be {self.expected}. "
            f"Got {self.actual!r}. {self.suggestion}"
        )


class ConfigValidationException(ToolExecutionError):
    def __init__(
        self,
        error: ErrorResponse,
        validation_errors: list[ConfigValidationError] | None = None,
    ):
        super().__init__(error)
        self.validation_errors = validation_errors or []


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
        errors.extend(self._missing_required_field_errors(data))
        vault_path = self._validated_vault_path(data, errors)
        self._validate_index_db_location(data, vault_path, errors)
        self._validate_context_packs(data, errors)
        self._validate_write_constraints(data, errors)
        self._validate_optional_fields(data, errors)
        return errors

    def validate(self, data: Any) -> ProjectConfig:
        errors = self.collect_errors(data)
        if errors:
            raise ConfigValidationException(_validation_error_response(errors), errors)

        vault_path = Path(data["vault_path"]).resolve()
        return ProjectConfig(
            vault_path=vault_path,
            index_db_location=_resolve_config_path(
                vault_path, data["index_db_location"]
            ),
            context_packs=_parse_context_packs(data["context_packs"]),
            write_constraints=_parse_write_constraints(data["write_constraints"]),
            tags_separator=data.get("tags_separator", DEFAULT_TAGS_SEPARATOR),
            max_proposal_ttl_hours=data.get(
                "max_proposal_ttl_hours",
                DEFAULT_MAX_PROPOSAL_TTL_HOURS,
            ),
        )

    @staticmethod
    def _missing_required_field_errors(
        data: dict[str, Any],
    ) -> list[ConfigValidationError]:
        return [
            ConfigValidationError(
                field=field_name,
                expected="present",
                actual="<missing>",
                suggestion=f"Add required field '{field_name}' to memory-mcp.yaml.",
            )
            for field_name in (
                "vault_path",
                "index_db_location",
                "context_packs",
                "write_constraints",
            )
            if field_name not in data
        ]

    def _validated_vault_path(
        self,
        data: dict[str, Any],
        errors: list[ConfigValidationError],
    ) -> Path | None:
        if "vault_path" not in data:
            return None

        vault_path = data["vault_path"]
        if not isinstance(vault_path, str):
            errors.append(
                _type_error("vault_path", "a string absolute path", vault_path)
            )
            return None

        candidate = Path(vault_path)
        if not candidate.is_absolute():
            errors.append(
                ConfigValidationError(
                    field="vault_path",
                    expected="an absolute path",
                    actual=vault_path,
                    suggestion="Use '/full/path' instead.",
                )
            )
            return None

        resolved = candidate.resolve(strict=False)
        if not resolved.is_dir():
            errors.append(
                ConfigValidationError(
                    field="vault_path",
                    expected="an existing directory",
                    actual=vault_path,
                    suggestion="Create the vault directory or point vault_path at an existing vault.",
                )
            )
            return None

        return resolved

    def _validate_index_db_location(
        self,
        data: dict[str, Any],
        vault_path: Path | None,
        errors: list[ConfigValidationError],
    ) -> None:
        if "index_db_location" not in data:
            return

        index_db_location = data["index_db_location"]
        if not isinstance(index_db_location, str) or not index_db_location:
            errors.append(
                _type_error(
                    "index_db_location", "a non-empty string path", index_db_location
                )
            )
            return

        if vault_path is None:
            return

        resolved = _resolve_config_path(vault_path, index_db_location)
        if not resolved.is_relative_to(vault_path):
            errors.append(
                ConfigValidationError(
                    field="index_db_location",
                    expected="a path inside vault_path",
                    actual=index_db_location,
                    suggestion="Use a relative path such as 'memory-index.sqlite3'.",
                )
            )

    def _validate_context_packs(
        self,
        data: dict[str, Any],
        errors: list[ConfigValidationError],
    ) -> None:
        if "context_packs" not in data:
            return

        context_packs = data["context_packs"]
        if not isinstance(context_packs, list):
            errors.append(
                _type_error(
                    "context_packs", "a list of context pack objects", context_packs
                )
            )
            return

        names: set[str] = set()
        includes_by_name: dict[str, tuple[int, tuple[str, ...]]] = {}
        for index, context_pack in enumerate(context_packs):
            if not isinstance(context_pack, dict):
                errors.append(
                    _type_error(f"context_packs[{index}]", "an object", context_pack)
                )
                continue

            name = context_pack.get("name")
            name_is_unique = False
            if not isinstance(name, str) or not name:
                errors.append(
                    _type_error(
                        f"context_packs[{index}].name", "a non-empty string", name
                    )
                )
            elif name in names:
                errors.append(
                    ConfigValidationError(
                        field=f"context_packs[{index}].name",
                        expected="a unique context pack name",
                        actual=name,
                        suggestion="Rename the duplicate context pack.",
                    )
                )
            else:
                names.add(name)
                name_is_unique = True

            self._validate_string_list(
                context_pack,
                "paths",
                f"context_packs[{index}].paths",
                errors,
                require_non_empty=True,
            )
            self._validate_string_list(
                context_pack,
                "include_context_packs",
                f"context_packs[{index}].include_context_packs",
                errors,
            )
            self._validate_optional_positive_int(
                context_pack,
                "token_budget",
                f"context_packs[{index}].token_budget",
                errors,
            )

            if name_is_unique and isinstance(name, str):
                includes = context_pack.get("include_context_packs", [])
                if isinstance(includes, list) and all(
                    isinstance(item, str) for item in includes
                ):
                    includes_by_name[name] = (index, tuple(includes))

        self._validate_context_pack_references(includes_by_name, names, errors)

    def _validate_context_pack_references(
        self,
        includes_by_name: dict[str, tuple[int, tuple[str, ...]]],
        names: set[str],
        errors: list[ConfigValidationError],
    ) -> None:
        for _pack_name, (original_index, includes) in includes_by_name.items():
            unknown = sorted(set(includes).difference(names))
            if unknown:
                errors.append(
                    ConfigValidationError(
                        field=f"context_packs[{original_index}].include_context_packs",
                        expected="names of defined context packs; unknown context pack references are invalid",
                        actual=unknown,
                        suggestion="Define the referenced context pack or remove the reference.",
                    )
                )

        include_graph = {
            name: includes
            for name, (_original_index, includes) in includes_by_name.items()
        }
        cycle = _find_context_pack_cycle(include_graph)
        if cycle:
            errors.append(
                ConfigValidationError(
                    field="context_packs",
                    expected="an acyclic include graph",
                    actual=" -> ".join(cycle),
                    suggestion="Remove one include_context_packs entry to break the circular reference.",
                )
            )

    def _validate_write_constraints(
        self,
        data: dict[str, Any],
        errors: list[ConfigValidationError],
    ) -> None:
        if "write_constraints" not in data:
            return

        write_constraints = data["write_constraints"]
        if not isinstance(write_constraints, dict):
            errors.append(
                _type_error(
                    "write_constraints",
                    "an object with read/write policies",
                    write_constraints,
                )
            )
            return

        for operation in ("read", "write"):
            policy = write_constraints.get(operation, {})
            if not isinstance(policy, dict):
                errors.append(
                    _type_error(f"write_constraints.{operation}", "an object", policy)
                )
                continue
            self._validate_string_list(
                policy, "allow", f"write_constraints.{operation}.allow", errors
            )
            self._validate_string_list(
                policy, "deny", f"write_constraints.{operation}.deny", errors
            )

    def _validate_optional_fields(
        self,
        data: dict[str, Any],
        errors: list[ConfigValidationError],
    ) -> None:
        if "tags_separator" in data and not isinstance(data["tags_separator"], str):
            errors.append(
                _type_error("tags_separator", "a string", data["tags_separator"])
            )
        self._validate_optional_positive_int(
            data,
            "max_proposal_ttl_hours",
            "max_proposal_ttl_hours",
            errors,
        )

    @staticmethod
    def _validate_string_list(
        container: dict[str, Any],
        key: str,
        field_path: str,
        errors: list[ConfigValidationError],
        *,
        require_non_empty: bool = False,
    ) -> None:
        if key not in container:
            if require_non_empty:
                errors.append(
                    ConfigValidationError(
                        field=field_path,
                        expected="a non-empty list of strings",
                        actual="<missing>",
                        suggestion=f"Add at least one path pattern to '{field_path}'.",
                    )
                )
            return

        value = container[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            errors.append(_type_error(field_path, "a list of strings", value))
            return

        if require_non_empty and not value:
            errors.append(
                ConfigValidationError(
                    field=field_path,
                    expected="a non-empty list of strings",
                    actual=value,
                    suggestion=f"Add at least one path pattern to '{field_path}'.",
                )
            )

    @staticmethod
    def _validate_optional_positive_int(
        container: dict[str, Any],
        key: str,
        field_path: str,
        errors: list[ConfigValidationError],
    ) -> None:
        if key not in container:
            return
        value = container[key]
        if not isinstance(value, int) or value <= 0:
            errors.append(_type_error(field_path, "a positive integer", value))


def _type_error(field: str, expected: str, actual: Any) -> ConfigValidationError:
    return ConfigValidationError(
        field=field,
        expected=expected,
        actual=actual,
        suggestion=f"Change '{field}' to the expected type or format: {expected}.",
    )


def _resolve_config_path(vault_path: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (vault_path / path).resolve(strict=False)


def _parse_context_packs(data: list[dict[str, Any]]) -> tuple[ContextPackConfig, ...]:
    return tuple(
        ContextPackConfig(
            name=context_pack["name"],
            paths=tuple(context_pack["paths"]),
            include_context_packs=tuple(context_pack.get("include_context_packs", ())),
            token_budget=context_pack.get("token_budget"),
        )
        for context_pack in data
    )


def _parse_write_constraints(data: dict[str, Any]) -> AccessConstraints:
    return AccessConstraints(
        read=_parse_access_policy(data.get("read", {})),
        write=_parse_access_policy(data.get("write", {})),
    )


def _parse_access_policy(data: dict[str, Any]) -> AccessPolicy:
    return AccessPolicy(
        allow=tuple(data.get("allow", ())),
        deny=tuple(data.get("deny", ())),
    )


def _find_context_pack_cycle(includes_by_name: dict[str, tuple[str, ...]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(name: str) -> list[str]:
        if name in visiting:
            start = path.index(name)
            return [*path[start:], name]
        if name in visited:
            return []

        visiting.add(name)
        path.append(name)
        for child in includes_by_name.get(name, ()):
            cycle = visit(child)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(name)
        visited.add(name)
        return []

    for pack_name in includes_by_name:
        cycle = visit(pack_name)
        if cycle:
            return cycle
    return []


def _validation_error_response(errors: list[ConfigValidationError]) -> ErrorResponse:
    field_names = ", ".join(error.field for error in errors[:5])
    if len(errors) > 5:
        field_names = f"{field_names}, ..."

    return build_error(
        ErrorCode.ERR_INVALID_PROJECT,
        message=f"Project config is invalid. Fix these field(s): {field_names}.",
        details={
            "errors": [error.message for error in errors],
            "suggestion": "Fix all listed fields, then run 'mcp-memory config validate' again.",
        },
    )
