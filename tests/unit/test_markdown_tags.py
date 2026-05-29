from __future__ import annotations

from obsidian_memory_mcp.markdown import tag_values_from_field


def test_tag_values_from_field_returns_empty_for_none() -> None:
    assert tag_values_from_field(None) == set()


def test_tag_values_from_field_parses_comma_separated_string() -> None:
    assert tag_values_from_field("api, public") == {"api", "public"}


def test_tag_values_from_field_parses_list() -> None:
    assert tag_values_from_field(["API", "public"]) == {"API", "public"}


def test_tag_values_from_field_parses_scalar() -> None:
    assert tag_values_from_field("solo") == {"solo"}


def test_tag_values_from_field_strips_hash_prefix() -> None:
    assert tag_values_from_field("#api") == {"api"}
