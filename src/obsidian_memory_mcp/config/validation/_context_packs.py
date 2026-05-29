"""Validation for context pack declarations."""

from __future__ import annotations

from typing import Any

from obsidian_memory_mcp.config.validation._errors import ConfigValidationError
from obsidian_memory_mcp.config.validation._rules import (
    find_context_pack_cycle,
    type_error,
    validate_optional_positive_int,
    validate_optional_string,
    validate_string_list,
)


def validate_context_packs(
    data: dict[str, Any],
    errors: list[ConfigValidationError],
) -> None:
    if "context_packs" not in data:
        return

    context_packs = data["context_packs"]
    if not isinstance(context_packs, list):
        errors.append(
            type_error(
                "context_packs", "a list of context pack objects", context_packs
            )
        )
        return

    names: set[str] = set()
    includes_by_name: dict[str, tuple[int, tuple[str, ...]]] = {}
    for index, context_pack in enumerate(context_packs):
        _validate_context_pack_entry(
            index,
            context_pack,
            names,
            includes_by_name,
            errors,
        )

    _validate_context_pack_references(includes_by_name, names, errors)


def _validate_context_pack_entry(
    index: int,
    context_pack: object,
    names: set[str],
    includes_by_name: dict[str, tuple[int, tuple[str, ...]]],
    errors: list[ConfigValidationError],
) -> None:
    if not isinstance(context_pack, dict):
        errors.append(type_error(f"context_packs[{index}]", "an object", context_pack))
        return

    name = context_pack.get("name")
    name_is_unique = False
    if not isinstance(name, str) or not name:
        errors.append(
            type_error(f"context_packs[{index}].name", "a non-empty string", name)
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

    prefix = f"context_packs[{index}]"
    validate_string_list(
        context_pack,
        "paths",
        f"{prefix}.paths",
        errors,
        require_non_empty=True,
    )
    validate_optional_string(
        context_pack, "description", f"{prefix}.description", errors
    )
    validate_string_list(context_pack, "sections", f"{prefix}.sections", errors)
    validate_string_list(
        context_pack, "tags_filter", f"{prefix}.tags_filter", errors
    )
    validate_string_list(
        context_pack,
        "include_context_packs",
        f"{prefix}.include_context_packs",
        errors,
    )
    validate_optional_positive_int(
        context_pack, "token_budget", f"{prefix}.token_budget", errors
    )

    if not name_is_unique or not isinstance(name, str):
        return

    includes = context_pack.get("include_context_packs", [])
    if isinstance(includes, list) and all(isinstance(item, str) for item in includes):
        includes_by_name[name] = (index, tuple(includes))


def _validate_context_pack_references(
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
                    expected=(
                        "names of defined context packs; unknown context pack "
                        "references are invalid"
                    ),
                    actual=unknown,
                    suggestion=(
                        "Define the referenced context pack or remove the reference."
                    ),
                )
            )

    include_graph = {
        name: includes
        for name, (_original_index, includes) in includes_by_name.items()
    }
    cycle = find_context_pack_cycle(include_graph)
    if cycle:
        errors.append(
            ConfigValidationError(
                field="context_packs",
                expected="an acyclic include graph",
                actual=" -> ".join(cycle),
                suggestion="Remove one include_context_packs entry to break the circular reference.",
            )
        )
