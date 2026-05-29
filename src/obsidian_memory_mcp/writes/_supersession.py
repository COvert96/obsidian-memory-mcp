"""SupersessionService — archive superseded memory notes and link successors.

The two-step ``plan()`` / ``commit()`` API lets the ``update_memory``
orchestrator interleave the new-note write between pre-flight validation and the
archive write phase (see PRD FR-2a):

    plan()  -> validate every input, compute archive destinations (no disk I/O)
    commit() -> move files, stamp frontmatter, back-reference the new note

``archive()`` bundles both phases for callers that do not need to write between
them.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.utils import normalize_vault_path
from obsidian_memory_mcp.writes._io import atomic_write


@dataclass(frozen=True)
class ArchiveMove:
    """One planned (source -> archive destination) relocation."""

    source: Path
    source_relative: str
    destination: Path
    destination_relative: str


@dataclass(frozen=True)
class SupersessionPlan:
    """The validated, side-effect-free output of :meth:`SupersessionService.plan`."""

    moves: tuple[ArchiveMove, ...]


class SupersessionService:
    def __init__(
        self, config: ProjectConfig, guardrails: GuardrailEvaluator
    ) -> None:
        self._config = config
        self._guardrails = guardrails

    def plan(
        self, superseded_paths: list[str], new_path: str
    ) -> SupersessionPlan:
        """Validate every input and compute archive destinations.

        Performs no disk writes. Raises immediately on the first invalid path so
        that no partial plan escapes.
        """
        new_relative = self._normalize_relative(new_path)
        archive_dir = self._archive_directory()

        moves: list[ArchiveMove] = []
        seen_sources: set[str] = set()
        planned_destinations: set[str] = set()
        for raw_path in superseded_paths:
            source = self._guardrails.check_write(raw_path)
            source_relative = source.relative_to(self._config.vault_path).as_posix()

            if source_relative == new_relative:
                raise ToolExecutionError(
                    build_error(
                        ErrorCode.ERR_INVALID_REQUEST,
                        message=(
                            "A note cannot supersede itself. "
                            f"Received '{source_relative}'."
                        ),
                        details={"file_path": source_relative},
                    )
                )

            if source_relative in seen_sources:
                continue
            seen_sources.add(source_relative)

            if not source.is_file():
                raise ToolExecutionError(
                    build_error(
                        ErrorCode.ERR_MISSING_FILE,
                        details={"file_path": source_relative},
                    )
                )

            destination = self._unique_destination(
                archive_dir, source.name, planned_destinations
            )
            destination_relative = destination.relative_to(
                self._config.vault_path
            ).as_posix()
            planned_destinations.add(destination_relative)
            moves.append(
                ArchiveMove(
                    source=source,
                    source_relative=source_relative,
                    destination=destination,
                    destination_relative=destination_relative,
                )
            )

        return SupersessionPlan(moves=tuple(moves))

    def commit(
        self, plan: SupersessionPlan, new_path: str, written_at: datetime
    ) -> list[str]:
        """Execute the archive write phase for a previously computed plan.

        Moves each superseded note into the archive, stamps it with supersession
        frontmatter, and finally back-references the new note. On any failure,
        best-effort rolls back completed moves and raises ``ERR_INTERNAL``.
        """
        new_relative = self._normalize_relative(new_path)
        stamped_at = _to_iso_utc(written_at)
        completed: list[ArchiveMove] = []
        try:
            for move in plan.moves:
                move.destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(move.source), str(move.destination))
                completed.append(move)
                _merge_frontmatter_file(
                    move.destination,
                    {
                        "superseded": True,
                        "superseded_by": new_relative,
                        "superseded_at": stamped_at,
                    },
                )

            archived_paths = [move.destination_relative for move in plan.moves]
            self._back_reference_new_note(new_path, archived_paths)
            return archived_paths
        except Exception as error:  # noqa: BLE001 — translated to ERR_INTERNAL
            raise self._rollback(completed, error) from error

    def archive(
        self, superseded_paths: list[str], new_path: str, written_at: datetime
    ) -> list[str]:
        """Convenience wrapper running :meth:`plan` then :meth:`commit`."""
        plan = self.plan(superseded_paths, new_path)
        return self.commit(plan, new_path, written_at)

    def _back_reference_new_note(
        self, new_path: str, archived_paths: list[str]
    ) -> None:
        new_target = self._guardrails.check_write(new_path)
        _merge_frontmatter_file(new_target, {"supersedes": archived_paths})

    def _rollback(
        self, completed: list[ArchiveMove], error: Exception
    ) -> ToolExecutionError:
        unrecovered: list[str] = []
        for move in completed:
            try:
                move.source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(move.destination), str(move.source))
            except Exception:  # noqa: BLE001 — record and continue best-effort
                unrecovered.append(move.destination_relative)

        details: dict[str, Any] = {"cause": str(error)}
        if unrecovered:
            details["unrecovered_archive_files"] = unrecovered
        return ToolExecutionError(
            build_error(
                ErrorCode.ERR_INTERNAL,
                message=(
                    "Supersession archive failed and was rolled back."
                    if not unrecovered
                    else (
                        "Supersession archive failed and could not be fully "
                        "rolled back; some files remain in the archive."
                    )
                ),
                details=details,
            )
        )

    def _archive_directory(self) -> Path:
        return normalize_vault_path(
            self._config.vault_path, self._config.memory_archive_path
        )

    def _unique_destination(
        self, archive_dir: Path, filename: str, planned: set[str]
    ) -> Path:
        candidate = archive_dir / filename
        candidate_relative = candidate.relative_to(
            self._config.vault_path
        ).as_posix()
        if not candidate.exists() and candidate_relative not in planned:
            return candidate

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        while True:
            disambiguated = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            candidate = archive_dir / disambiguated
            candidate_relative = candidate.relative_to(
                self._config.vault_path
            ).as_posix()
            if not candidate.exists() and candidate_relative not in planned:
                return candidate

    def _normalize_relative(self, file_path: str) -> str:
        resolved = normalize_vault_path(self._config.vault_path, file_path)
        return resolved.relative_to(self._config.vault_path).as_posix()


def _merge_frontmatter_file(path: Path, updates: dict[str, Any]) -> None:
    merged = _apply_frontmatter(path.read_text(encoding="utf-8"), updates)
    atomic_write(path, merged.encode("utf-8"))


def _apply_frontmatter(text: str, updates: dict[str, Any]) -> str:
    metadata, body = _split_frontmatter(text)
    metadata.update(updates)
    rendered = yaml.dump(
        metadata, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    return f"---\n{rendered}---\n{body}"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw_metadata = "".join(lines[1:index])
            loaded = yaml.safe_load(raw_metadata) if raw_metadata.strip() else {}
            metadata = loaded if isinstance(loaded, dict) else {}
            return dict(metadata), "".join(lines[index + 1 :])
    return {}, text


def _to_iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
