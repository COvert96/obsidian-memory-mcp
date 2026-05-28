"""Initial schema for v0.2.0."""

from __future__ import annotations

from typing import Final

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: None = None
depends_on: None = None

_INDEX_NAMES: Final[tuple[str, ...]] = (
    "idx_proposal_changeset_events_changeset_id",
    "idx_proposal_changeset_members_proposal",
    "idx_proposal_changeset_members_changeset",
    "idx_proposal_changesets_status_created",
    "idx_proposal_events_proposal_id",
    "idx_proposals_created",
    "idx_proposals_file_path",
    "idx_proposals_status_created",
    "idx_index_errors_file_id",
    "idx_index_errors_run_id",
    "idx_wikilinks_file_id",
    "idx_wikilinks_target",
    "idx_blocks_section_id",
    "idx_blocks_file_id",
    "idx_sections_file_id",
    "idx_files_freshness",
)

_TABLE_NAMES: Final[tuple[str, ...]] = (
    "write_audit",
    "proposal_changeset_events",
    "proposal_changeset_members",
    "proposal_changesets",
    "proposal_events",
    "proposals",
    "wikilinks",
    "blocks",
    "sections",
    "index_errors",
    "files",
    "index_runs",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
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
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
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
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
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
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
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
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wikilinks (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            vault_path TEXT NOT NULL,
            section_key TEXT NOT NULL,
            target TEXT NOT NULL,
            alias TEXT,
            raw TEXT NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS index_errors (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            file_id INTEGER,
            vault_path TEXT,
            error_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES index_runs(id),
            FOREIGN KEY(file_id) REFERENCES files(id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT NOT NULL PRIMARY KEY,
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
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposal_events (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            details TEXT NOT NULL,
            FOREIGN KEY(proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposal_changesets (
            id TEXT NOT NULL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status_changed_at TEXT
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposal_changeset_members (
            changeset_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            PRIMARY KEY (changeset_id, proposal_id),
            FOREIGN KEY(changeset_id) REFERENCES proposal_changesets(id) ON DELETE CASCADE,
            FOREIGN KEY(proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposal_changeset_events (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            changeset_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            details TEXT NOT NULL,
            FOREIGN KEY(changeset_id) REFERENCES proposal_changesets(id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS write_audit (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            tool TEXT NOT NULL,
            project TEXT NOT NULL,
            file_path TEXT NOT NULL,
            operation TEXT NOT NULL,
            content_hash TEXT,
            supersedes TEXT
        )
        """
    )

    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
            block_key UNINDEXED,
            vault_path UNINDEXED,
            section_path,
            heading,
            content,
            tags
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_files_freshness
            ON files(vault_path, size_bytes, mtime_ns, parser_version, deleted_at)
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sections_file_id ON sections(file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_blocks_file_id ON blocks(file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_blocks_section_id ON blocks(section_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wikilinks_target ON wikilinks(target)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wikilinks_file_id ON wikilinks(file_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_index_errors_run_id ON index_errors(run_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_index_errors_file_id ON index_errors(file_id)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_proposals_status_created
            ON proposals(status, created_at DESC)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposals_file_path ON proposals(file_path)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at DESC)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal_id
            ON proposal_events(proposal_id, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_proposal_changesets_status_created
            ON proposal_changesets(status, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_proposal_changeset_members_changeset
            ON proposal_changeset_members(changeset_id, ordinal)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_proposal_changeset_members_proposal
            ON proposal_changeset_members(proposal_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_proposal_changeset_events_changeset_id
            ON proposal_changeset_events(changeset_id, id)
        """
    )


def downgrade() -> None:
    for index_name in _INDEX_NAMES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    op.execute("DROP TABLE IF EXISTS blocks_fts")

    for table_name in _TABLE_NAMES:
        op.execute(f"DROP TABLE IF EXISTS {table_name}")
