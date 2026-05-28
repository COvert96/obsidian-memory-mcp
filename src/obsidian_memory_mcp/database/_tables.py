"""Shared SQLAlchemy Core table metadata."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    text,
)
from sqlalchemy.engine import Connection

metadata = MetaData()

index_runs = Table(
    "index_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("mode", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text, nullable=True),
    Column("parser_version", Text, nullable=False),
    Column("files_seen", Integer, nullable=False, server_default=text("0")),
    Column("files_processed", Integer, nullable=False, server_default=text("0")),
    Column("files_skipped", Integer, nullable=False, server_default=text("0")),
    Column("files_deleted", Integer, nullable=False, server_default=text("0")),
    Column("files_failed", Integer, nullable=False, server_default=text("0")),
    Column("sections_indexed", Integer, nullable=False, server_default=text("0")),
    Column("blocks_indexed", Integer, nullable=False, server_default=text("0")),
    Column("errors", Integer, nullable=False, server_default=text("0")),
    Column("duration_ms", Integer, nullable=False, server_default=text("0")),
    sqlite_autoincrement=True,
)

files = Table(
    "files",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("vault_path", Text, nullable=False, unique=True),
    Column("size_bytes", Integer, nullable=False),
    Column("mtime_ns", Integer, nullable=False),
    Column("file_hash", Text, nullable=True),
    Column("raw_content_hash", Text, nullable=True),
    Column("normalized_content_hash", Text, nullable=True),
    Column("parser_version", Text, nullable=False),
    Column("indexed_at", Text, nullable=False),
    Column("deleted_at", Text, nullable=True),
    Column("last_run_id", Integer, ForeignKey("index_runs.id"), nullable=True),
    Column("last_error_id", Integer, ForeignKey("index_errors.id"), nullable=True),
    sqlite_autoincrement=True,
)

sections = Table(
    "sections",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "file_id", Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    ),
    Column("vault_path", Text, nullable=False),
    Column("section_key", Text, nullable=False, unique=True),
    Column("section_path", Text, nullable=False),
    Column("heading", Text, nullable=True),
    Column("heading_slug", Text, nullable=False),
    Column("heading_ordinal", Integer, nullable=False),
    Column("level", Integer, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("start_line", Integer, nullable=False),
    Column("end_line", Integer, nullable=False),
    sqlite_autoincrement=True,
)

blocks = Table(
    "blocks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "file_id", Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    ),
    Column(
        "section_id",
        Integer,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("vault_path", Text, nullable=False),
    Column("section_key", Text, nullable=False),
    Column("section_path", Text, nullable=False),
    Column("block_key", Text, nullable=False, unique=True),
    Column("heading", Text, nullable=True),
    Column("content", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("token_count_estimate", Integer, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("tags", Text, nullable=False),
    sqlite_autoincrement=True,
)

wikilinks = Table(
    "wikilinks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "file_id", Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    ),
    Column(
        "section_id",
        Integer,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("vault_path", Text, nullable=False),
    Column("section_key", Text, nullable=False),
    Column("target", Text, nullable=False),
    Column("alias", Text, nullable=True),
    Column("raw", Text, nullable=False),
    sqlite_autoincrement=True,
)

index_errors = Table(
    "index_errors",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("index_runs.id"), nullable=False),
    Column("file_id", Integer, ForeignKey("files.id"), nullable=True),
    Column("vault_path", Text, nullable=True),
    Column("error_type", Text, nullable=False),
    Column("message", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    sqlite_autoincrement=True,
)

proposals = Table(
    "proposals",
    metadata,
    Column("id", Text, primary_key=True),
    Column("file_path", Text, nullable=False),
    Column("operation", Text, nullable=False),
    Column("content", Text, nullable=True),
    Column("old_hash", Text, nullable=True),
    Column("new_hash", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
    Column("status_changed_at", Text, nullable=True),
    Column("applied_at", Text, nullable=True),
)

proposal_events = Table(
    "proposal_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "proposal_id",
        Text,
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("details", Text, nullable=False),
    sqlite_autoincrement=True,
)

proposal_changesets = Table(
    "proposal_changesets",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
    Column("status_changed_at", Text, nullable=True),
)

proposal_changeset_members = Table(
    "proposal_changeset_members",
    metadata,
    Column(
        "changeset_id",
        Text,
        ForeignKey("proposal_changesets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "proposal_id",
        Text,
        ForeignKey("proposals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, nullable=False),
    Column("role", Text, nullable=False, server_default=text("'member'")),
)

proposal_changeset_events = Table(
    "proposal_changeset_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "changeset_id",
        Text,
        ForeignKey("proposal_changesets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("details", Text, nullable=False),
    sqlite_autoincrement=True,
)

Index(
    "idx_files_freshness",
    files.c.vault_path,
    files.c.size_bytes,
    files.c.mtime_ns,
    files.c.parser_version,
    files.c.deleted_at,
)
Index("idx_sections_file_id", sections.c.file_id)
Index("idx_blocks_file_id", blocks.c.file_id)
Index("idx_blocks_section_id", blocks.c.section_id)
Index("idx_wikilinks_target", wikilinks.c.target)
Index("idx_wikilinks_file_id", wikilinks.c.file_id)
Index("idx_index_errors_run_id", index_errors.c.run_id)
Index("idx_index_errors_file_id", index_errors.c.file_id)
Index("idx_proposals_status_created", proposals.c.status, proposals.c.created_at.desc())
Index("idx_proposals_file_path", proposals.c.file_path)
Index("idx_proposals_created", proposals.c.created_at.desc())
Index(
    "idx_proposal_events_proposal_id",
    proposal_events.c.proposal_id,
    proposal_events.c.id,
)
Index(
    "idx_proposal_changesets_status_created",
    proposal_changesets.c.status,
    proposal_changesets.c.created_at.desc(),
)
Index(
    "idx_proposal_changeset_members_changeset",
    proposal_changeset_members.c.changeset_id,
    proposal_changeset_members.c.ordinal,
)
Index(
    "idx_proposal_changeset_members_proposal",
    proposal_changeset_members.c.proposal_id,
)
Index(
    "idx_proposal_changeset_events_changeset_id",
    proposal_changeset_events.c.changeset_id,
    proposal_changeset_events.c.id,
)


def create_fts_tables(connection: Connection) -> None:
    # FTS5 virtual-table DDL is an intentional SQL text exception: SQLAlchemy Core
    # cannot model CREATE VIRTUAL TABLE ... USING fts5(...).
    connection.execute(
        text(
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
    )
