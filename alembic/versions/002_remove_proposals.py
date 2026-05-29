"""Drop the proposal workflow tables (Phase 8c).

Self-contained: the upgrade and downgrade DDL is inlined here rather than
reflected from shared metadata, because Phase 8c deletes the proposal ``Table``
definitions from ``database/_tables.py`` once this migration ships.
"""

from __future__ import annotations

from typing import Final

from alembic import op

revision: str = "002_remove_proposals"
down_revision: str | None = "001_initial_schema"
branch_labels: None = None
depends_on: None = None

# SQLite enforces foreign keys child-first: drop dependents before parents.
_DROP_TABLE_ORDER: Final[tuple[str, ...]] = (
    "proposal_changeset_events",
    "proposal_changeset_members",
    "proposal_changesets",
    "proposal_events",
    "proposals",
)

_RECREATE_INDEX_STATEMENTS: Final[tuple[str, ...]] = (
    """
    CREATE INDEX IF NOT EXISTS idx_proposals_status_created
        ON proposals(status, created_at DESC)
    """,
    "CREATE INDEX IF NOT EXISTS idx_proposals_file_path ON proposals(file_path)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at DESC)",
    """
    CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal_id
        ON proposal_events(proposal_id, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_proposal_changesets_status_created
        ON proposal_changesets(status, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_proposal_changeset_members_changeset
        ON proposal_changeset_members(changeset_id, ordinal)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_proposal_changeset_members_proposal
        ON proposal_changeset_members(proposal_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_proposal_changeset_events_changeset_id
        ON proposal_changeset_events(changeset_id, id)
    """,
)


def upgrade() -> None:
    for table_name in _DROP_TABLE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table_name}")


def downgrade() -> None:
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
    for statement in _RECREATE_INDEX_STATEMENTS:
        op.execute(statement)
