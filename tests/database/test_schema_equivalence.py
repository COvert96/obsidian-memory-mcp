from __future__ import annotations

import sqlite3
from pathlib import Path

from obsidian_memory_mcp.schema import SCHEMA_VERSION, bootstrap_schema

LEGACY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS index_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    parser_version TEXT NOT NULL,
    files_seen INTEGER NOT NULL DEFAULT 0,
    files_processed INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    files_deleted INTEGER NOT NULL DEFAULT 0,
    files_failed INTEGER NOT NULL DEFAULT 0,
    sections_indexed INTEGER NOT NULL DEFAULT 0,
    blocks_indexed INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vault_path TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    file_hash TEXT,
    raw_content_hash TEXT,
    normalized_content_hash TEXT,
    parser_version TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    deleted_at TEXT,
    last_run_id INTEGER,
    last_error_id INTEGER,
    FOREIGN KEY(last_run_id) REFERENCES index_runs(id),
    FOREIGN KEY(last_error_id) REFERENCES index_errors(id)
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    vault_path TEXT NOT NULL,
    section_key TEXT NOT NULL UNIQUE,
    section_path TEXT NOT NULL,
    heading TEXT,
    heading_slug TEXT NOT NULL,
    heading_ordinal INTEGER NOT NULL,
    level INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    vault_path TEXT NOT NULL,
    section_key TEXT NOT NULL,
    section_path TEXT NOT NULL,
    block_key TEXT NOT NULL UNIQUE,
    heading TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    token_count_estimate INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    tags TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wikilinks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    vault_path TEXT NOT NULL,
    section_key TEXT NOT NULL,
    target TEXT NOT NULL,
    alias TEXT,
    raw TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS index_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    file_id INTEGER,
    vault_path TEXT,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES index_runs(id),
    FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
    block_key UNINDEXED,
    vault_path UNINDEXED,
    section_path,
    heading,
    content,
    tags
);

CREATE INDEX IF NOT EXISTS idx_files_freshness
    ON files(vault_path, size_bytes, mtime_ns, parser_version, deleted_at);
CREATE INDEX IF NOT EXISTS idx_sections_file_id
    ON sections(file_id);
CREATE INDEX IF NOT EXISTS idx_blocks_file_id
    ON blocks(file_id);
CREATE INDEX IF NOT EXISTS idx_blocks_section_id
    ON blocks(section_id);
CREATE INDEX IF NOT EXISTS idx_wikilinks_target
    ON wikilinks(target);
CREATE INDEX IF NOT EXISTS idx_wikilinks_file_id
    ON wikilinks(file_id);
CREATE INDEX IF NOT EXISTS idx_index_errors_run_id
    ON index_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_index_errors_file_id
    ON index_errors(file_id);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    operation TEXT NOT NULL,
    content TEXT,
    old_hash TEXT,
    new_hash TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status_changed_at TEXT,
    applied_at TEXT
);

CREATE TABLE IF NOT EXISTS proposal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    details TEXT NOT NULL,
    FOREIGN KEY(proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_proposals_status_created
    ON proposals(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_file_path
    ON proposals(file_path);
CREATE INDEX IF NOT EXISTS idx_proposals_created
    ON proposals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal_id
    ON proposal_events(proposal_id, id);

CREATE TABLE IF NOT EXISTS proposal_changesets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status_changed_at TEXT
);

CREATE TABLE IF NOT EXISTS proposal_changeset_members (
    changeset_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (changeset_id, proposal_id),
    FOREIGN KEY(changeset_id) REFERENCES proposal_changesets(id) ON DELETE CASCADE,
    FOREIGN KEY(proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS proposal_changeset_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changeset_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    details TEXT NOT NULL,
    FOREIGN KEY(changeset_id) REFERENCES proposal_changesets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_proposal_changesets_status_created
    ON proposal_changesets(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_changeset_members_changeset
    ON proposal_changeset_members(changeset_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_proposal_changeset_members_proposal
    ON proposal_changeset_members(proposal_id);
CREATE INDEX IF NOT EXISTS idx_proposal_changeset_events_changeset_id
    ON proposal_changeset_events(changeset_id, id);
"""


def test_schema_bootstrap_matches_legacy_executescript_shape(tmp_path: Path) -> None:
    sa_core_path = tmp_path / "sa-core.sqlite3"
    legacy_path = tmp_path / "legacy.sqlite3"

    sa_connection = sqlite3.connect(sa_core_path)
    legacy_connection = sqlite3.connect(legacy_path)
    try:
        bootstrap_schema(sa_connection)

        legacy_connection.executescript(LEGACY_SCHEMA_SQL)
        legacy_connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        legacy_connection.commit()

        assert _schema_snapshot(sa_connection) == _schema_snapshot(legacy_connection)
    finally:
        sa_connection.close()
        legacy_connection.close()


def test_bootstrap_schema_upgrades_user_version_3_to_current(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA user_version = 3")
        bootstrap_schema(connection)
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()

    assert user_version == SCHEMA_VERSION


def _schema_snapshot(connection: sqlite3.Connection) -> dict[str, object]:
    sqlite_master_rows = tuple(
        connection.execute(
            """
            SELECT type, name, tbl_name
            FROM sqlite_master
            WHERE type IN ('table', 'index', 'trigger', 'view')
            ORDER BY type, name, tbl_name
            """
        ).fetchall()
    )

    table_names = tuple(
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    )

    table_info = {
        table_name: tuple(
            sorted(
                (
                    (
                        int(row[0]),
                        str(row[1]),
                        str(row[2]),
                        0 if int(row[5]) == 1 else int(row[3]),
                        row[4],
                        int(row[5]),
                    )
                    for row in connection.execute(
                        f"PRAGMA table_info('{table_name}')"
                    ).fetchall()
                ),
                key=lambda row: (row[0], row[1]),
            )
        )
        for table_name in table_names
    }
    index_list = {
        table_name: tuple(
            sorted(
                (
                    (str(row[1]), int(row[2]), str(row[3]), int(row[4]))
                    for row in connection.execute(
                        f"PRAGMA index_list('{table_name}')"
                    ).fetchall()
                ),
                key=lambda row: row[0],
            )
        )
        for table_name in table_names
    }
    index_info = {
        index_name: tuple(
            sorted(
                connection.execute(f"PRAGMA index_info('{index_name}')").fetchall(),
                key=lambda row: (int(row[0]), int(row[1]), str(row[2])),
            )
        )
        for table_name in table_names
        for _, index_name, *_ in connection.execute(
            f"PRAGMA index_list('{table_name}')"
        ).fetchall()
    }

    return {
        "sqlite_master": sqlite_master_rows,
        "table_info": table_info,
        "index_list": index_list,
        "index_info": index_info,
    }
