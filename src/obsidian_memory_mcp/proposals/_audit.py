"""Shared helpers for proposal and changeset audit payloads."""

from __future__ import annotations

from typing import Any


def build_event_details(
    base: dict[str, Any],
    *,
    reason: str | None = None,
    notes: str | None = None,
    actor: str | None = None,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    details = dict(base)
    if reason:
        details["reason"] = reason
    if notes:
        details["notes"] = notes
    if actor:
        details["actor"] = actor
    if workflow_id:
        details["workflow_id"] = workflow_id
    return details
