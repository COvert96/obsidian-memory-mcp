"""SQLite index-query adapter for context-pack ranking and staleness checks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from obsidian_memory_mcp.database import connect_index_db


class SqliteIndexQueries:
    """SQLite adapter for context-pack index metadata and ranking queries."""

    def __init__(self, index_db_path: Path):
        self._index_db_path = index_db_path

    def bm25_ranks(
        self,
        query: str,
        vault_paths: tuple[str, ...],
    ) -> dict[str, float]:
        if not query or not vault_paths:
            return {}

        placeholders = ", ".join("?" for _ in vault_paths)
        sql = f"""
            SELECT blocks.vault_path, MIN(bm25(blocks_fts)) AS rank
            FROM blocks_fts
            JOIN blocks ON blocks.block_key = blocks_fts.block_key
            JOIN files ON files.id = blocks.file_id
            WHERE blocks_fts MATCH ?
              AND files.deleted_at IS NULL
              AND blocks.vault_path IN ({placeholders})
            GROUP BY blocks.vault_path
        """
        connection = connect_index_db(self._index_db_path)
        try:
            rows = connection.execute(sql, (query, *vault_paths)).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            connection.close()

        return {row["vault_path"]: float(row["rank"]) for row in rows}

    def indexed_at(self, vault_paths: tuple[str, ...]) -> dict[str, str]:
        if not vault_paths:
            return {}

        placeholders = ", ".join("?" for _ in vault_paths)
        sql = f"""
            SELECT vault_path, indexed_at
            FROM files
            WHERE deleted_at IS NULL
              AND vault_path IN ({placeholders})
        """
        connection = connect_index_db(self._index_db_path)
        try:
            rows = connection.execute(sql, vault_paths).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            connection.close()

        return {row["vault_path"]: row["indexed_at"] for row in rows}
