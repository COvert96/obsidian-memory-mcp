---
tags: [api, proposals, write]
type: reference
---
# Propose Memory Update

The Propose Memory Update endpoint allows clients to create a new proposal for writing, creating, or deleting a file in the Memory directory. This is the first step in the two-step proposal workflow.

## Overview

Before any changes are applied to disk, a proposal must be created and then approved. The propose endpoint validates the requested operation, checks vault boundaries, and returns a proposal ID that the client must present to the approval endpoint to make the changes permanent.

## Request Parameters

The proposal request accepts the following fields: `project` (required, string), `file_path` (required, string starting with `Memory/`), `operation` (required, one of `create`, `update`, or `delete`), and `content` (optional, required for create/update operations). The file path must be vault-relative and must start with `Memory/` — any path outside this directory is rejected with a guardrail error.

## Response Fields

A successful response includes `proposal_id`, `file_path`, `operation`, `created_at` timestamp, `expires_at` timestamp, and `content_hash`. The proposal ID is used in subsequent approval or rejection calls. Proposals automatically expire after a configurable duration (default 24 hours).

## Error Codes

Common errors include `INVALID_REQUEST` for malformed input, `OUT_OF_BOUNDS` when the path is outside Memory/, `CONFLICT` when the target already exists for create operations, and `NOT_FOUND` when the target does not exist for update/delete operations. See [[error-codes]] for complete error documentation.

## Example Usage

Clients should include the proposal ID in the approval request body along with the file path. For details on applying approved proposals to disk, see [[approval-process]] and [[retrieval-tools]].
