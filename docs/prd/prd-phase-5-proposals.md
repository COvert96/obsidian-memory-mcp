# PRD: Phase 5 - Proposal Workflow Overview

## Introduction

Phase 5 is now split into two documents so the core proposal engine is separated from higher-level workflow hardening.

- [Phase 5A PRD: Core Proposal Workflow](prd-phase-5a-proposals.md)
- [Phase 5B PRD: Advanced Proposal Workflows and Memory Supersession](prd-phase-5b-proposals.md)

## Why The Split Exists

The original Phase 5 scope mixed two different concerns:

1. The generic proposal engine needed to support safe, operator-approved writes.
2. Higher-level workflows such as `Memory/` supersession, grouped multi-file changes, and richer operator tooling.

Those concerns do not have the same implementation risk or product urgency.

## Phase 5A Summary

Phase 5A covers the smallest safe writable release:

- `propose_memory_update`
- `list_proposals`
- `approve_proposal`
- operator CLI reject for pending proposals (no structured notes in 5A)
- proposal persistence
- file-state conflict detection via `old_hash`
- expiry handling
- minimal lifecycle logging
- single-file create, update, and delete flows

Read [Phase 5A](prd-phase-5a-proposals.md) when you need the implementation plan for the base proposal engine.

## Phase 5B Summary

Phase 5B covers workflows that go beyond simple single-file mutation:

- grouped logical changesets
- contradiction-resolving `Memory/` workflows
- supersession and archival metadata conventions
- richer operator CLI and audit/reporting surfaces
- optional reject enrichment (structured reason/notes) beyond the baseline 5A reject behavior
- optional diff and batch approval features when justified by usage

Read [Phase 5B](prd-phase-5b-proposals.md) when you need the implementation plan for memory supersession or other higher-level workflow semantics.

## Decision Gate

Build Phase 5 only if a real write workflow exists that is not served well enough by manual copy-paste.

Build Phase 5B only after Phase 5A proves insufficient for a real workflow, such as contradiction-resolving `Memory/` management.
