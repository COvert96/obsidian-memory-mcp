"""Tests for tool contracts and the error catalog."""

from __future__ import annotations

from obsidian_memory_mcp.contracts import TOOL_CONTRACTS, TOOL_ERROR_CODES, ToolContract
from obsidian_memory_mcp.errors import ERROR_CATALOG, ErrorCode, build_error


EXPECTED_TOOL_NAMES = {
    "approve_proposal",
    "get_context_pack",
    "list_proposals",
    "propose_memory_update",
    "read_note",
    "read_section",
    "search_notes",
}


# ---------------------------------------------------------------------------
# Contract completeness
# ---------------------------------------------------------------------------


def test_all_expected_tools_are_registered() -> None:
    assert set(TOOL_CONTRACTS) == EXPECTED_TOOL_NAMES


def test_every_contract_has_a_non_empty_description() -> None:
    for name, contract in TOOL_CONTRACTS.items():
        assert contract.description, f"Tool '{name}' has an empty description."


def test_every_contract_declares_at_least_one_error_code() -> None:
    for name, contract in TOOL_CONTRACTS.items():
        assert contract.possible_errors, f"Tool '{name}' declares no possible errors."


def test_tool_error_codes_matches_contract_possible_errors() -> None:
    """TOOL_ERROR_CODES is derived from TOOL_CONTRACTS; verify the derivation is consistent."""
    for name, contract in TOOL_CONTRACTS.items():
        assert TOOL_ERROR_CODES[name] == contract.possible_errors


# ---------------------------------------------------------------------------
# Error catalog
# ---------------------------------------------------------------------------


def test_error_catalog_covers_all_error_codes() -> None:
    for code in ErrorCode:
        assert code in ERROR_CATALOG, f"ErrorCode {code!r} is missing from ERROR_CATALOG."


def test_error_catalog_entries_have_non_empty_recovery_suggestions() -> None:
    for code, definition in ERROR_CATALOG.items():
        assert definition.recovery_suggestion, f"{code!r} has an empty recovery_suggestion."


def test_error_template_placeholders_format_from_details() -> None:
    error = build_error(
        ErrorCode.ERR_MISSING_FILE,
        details={"file_path": "wiki/missing.md"},
    )
    assert error.message == "File 'wiki/missing.md' does not exist in the project vault."


def test_missing_placeholder_key_is_left_unchanged() -> None:
    # If a template key is absent from details, the placeholder should survive verbatim.
    error = build_error(ErrorCode.ERR_MISSING_FILE, details={})
    assert "{file_path}" in error.message
