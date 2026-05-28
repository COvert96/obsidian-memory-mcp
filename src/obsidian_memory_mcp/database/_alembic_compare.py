"""Alembic autogenerate comparison hooks for SQLite-specific behavior."""

from __future__ import annotations


def include_object_for_compare(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    del object_, compare_to
    if type_ == "table" and reflected and name is not None and name.startswith(
        "blocks_fts"
    ):
        return False
    return True


def compare_nullable_for_primary_keys(
    context: object,
    inspected_column: object,
    metadata_column: object,
    inspected_nullable: bool,
    metadata_nullable: bool,
    rendered_metadata_nullable: bool,
) -> bool | None:
    del context, inspected_nullable, metadata_nullable, rendered_metadata_nullable

    # SQLite reflection reports INTEGER/TEXT primary-key columns as nullable unless
    # NOT NULL is explicitly specified. Ignore nullable-only PK drift while still
    # keeping PK columns in autogenerate comparisons for all other differences.
    inspected_is_primary_key = bool(getattr(inspected_column, "primary_key", False))
    metadata_is_primary_key = bool(getattr(metadata_column, "primary_key", False))
    if inspected_is_primary_key and metadata_is_primary_key:
        return False
    return None
