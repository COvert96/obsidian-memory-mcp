from __future__ import annotations

from types import SimpleNamespace

from obsidian_memory_mcp.database._alembic_compare import (
    compare_nullable_for_primary_keys,
    include_object_for_compare,
)


def test_include_object_filters_reflected_fts_table() -> None:
    assert (
        include_object_for_compare(object(), "blocks_fts", "table", True, None) is False
    )


def test_include_object_keeps_primary_key_columns_in_comparison() -> None:
    reflected_column = SimpleNamespace(primary_key=True)
    metadata_column = SimpleNamespace(primary_key=True)

    assert (
        include_object_for_compare(
            reflected_column,
            "id",
            "column",
            True,
            metadata_column,
        )
        is True
    )


def test_compare_nullable_ignores_nullable_diff_for_primary_key_columns() -> None:
    reflected_column = SimpleNamespace(primary_key=True)
    metadata_column = SimpleNamespace(primary_key=True)

    assert (
        compare_nullable_for_primary_keys(
            None,
            reflected_column,
            metadata_column,
            True,
            False,
            False,
        )
        is False
    )


def test_compare_nullable_delegates_non_primary_key_columns() -> None:
    reflected_column = SimpleNamespace(primary_key=False)
    metadata_column = SimpleNamespace(primary_key=False)

    assert (
        compare_nullable_for_primary_keys(
            None,
            reflected_column,
            metadata_column,
            True,
            False,
            False,
        )
        is None
    )
