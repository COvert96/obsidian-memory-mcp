from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from obsidian_memory_mcp.proposals._db import bootstrap_schema_once
from obsidian_memory_mcp.schema import SchemaVersionError


def test_bootstrap_schema_once_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA user_version = 999")

    with pytest.raises(SchemaVersionError):
        bootstrap_schema_once(connection, database_path, database_existed=True)

    connection.close()
