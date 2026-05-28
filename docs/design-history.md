# Design History

This document preserves design context from pre-release phases that was trimmed from the concise MVP architecture reference.

## Problem Context

The project exists to provide AI clients with persistent project memory backed by markdown notes while keeping writes guarded and reviewable. The core tension throughout design was retrieval convenience versus filesystem safety.

## Why FastMCP

Earlier planning weighed building a custom MCP protocol layer against using the official SDK. The project standardized on FastMCP so JSON-RPC framing, transport behavior, handshake negotiation, and schema generation stay in maintained upstream code while local code focuses on vault policy and workflows.

## Why SQLite FTS

Release design favored deterministic local behavior over embedding infrastructure. SQLite FTS5 keeps indexing/search fully local, dependency-light, and reproducible across CI and operator machines.

## Why Proposal-Based Writes

The system separates proposal creation from write application to preserve human review, auditability, and hash-based conflict checks. This was chosen over direct writes to minimize accidental or unsafe memory mutations from automated agents.

## Why CLI-Driven Indexing

Indexing runs explicitly through CLI commands to avoid background watchers and process-lifecycle complexity in the MVP. This keeps operations predictable and easier to debug in cross-platform environments.

## Historical Risks Tracked

- Protocol-layer reinvention risk if not using the SDK.
- Relevance risk from pure lexical search.
- Stale-index risk without auto-watchers.
- Write-safety risk from direct mutation workflows.
- Scope creep risk during phased delivery.

## Evolution Paths Captured

The roadmap left room for semantic retrieval, automatic indexing triggers, richer multi-vault workflows, and hosted docs. These were intentionally deferred from MVP scope to prioritize deterministic behavior and release readiness.
