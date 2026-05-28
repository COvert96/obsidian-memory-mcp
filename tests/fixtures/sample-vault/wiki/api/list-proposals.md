---
tags: [api, proposals]
type: reference
---
# List Proposals

The List Proposals endpoint allows clients to query pending, approved, or rejected proposals. It supports filtering by status, file path, and project, making it easy to find proposals relevant to a specific workflow.

## Overview

List Proposals is used to monitor the state of pending changes across a project. It returns proposal metadata without the full content, reducing response size for high-volume queries. Clients typically use this endpoint to build approval dashboards or audit workflows.

## Filter Parameters

The endpoint accepts `project` (required), `status` (optional, one of `pending`, `applied`, `rejected`, or `expired`), `file_path` (optional, vault-relative path to filter by), and `limit` (optional, default 50). Filters are combined with AND logic — all specified conditions must match for a proposal to be included.

## Response Format

Results are returned as an array of proposal summaries. Each summary includes `proposal_id`, `file_path`, `operation`, `status`, `created_at`, `expires_at`, and `created_by`. Results are ordered by creation time (newest first) unless a different sort order is specified in the query.

## Status Values

Valid status values are `pending` (awaiting approval or rejection), `applied` (successfully written to disk), `rejected` (discarded by user), and `expired` (automatically expired after the retention period). See [[proposal-lifecycle]] for state transition details.

## Pagination

For large result sets, the endpoint returns a `next_cursor` token that can be passed in a subsequent request to retrieve the next page. This allows efficient iteration without loading all proposals into memory. See [[approve-reject-proposal]] and [[list-proposals]] documentation for examples.
