---
tags: [api, context-packs, retrieval]
type: reference
---
# Context Pack API

Context packs are pre-defined collections of markdown blocks extracted from the vault and returned with a single tool call. They are configured in the project's memory-mcp.yaml and optimized for specific use cases like onboarding or compliance review.

## Overview

The Context Pack API consists of two tools: `get_context_pack` retrieves a single named pack by project and name, and `list_context_packs` enumerates all packs available for a project. Context packs are designed to fit within token budgets by truncating or gracefully degrading when necessary.

## get_context_pack Tool

This tool accepts `project` (required) and `pack_name` (required) parameters. It returns the pack contents as formatted markdown blocks, ordered by relevance and rank. The optional `strict_budget` parameter controls behavior when the pack exceeds its token budget — `true` rejects the request with an error, `false` truncates the results to stay within budget.

## list_context_packs Tool

Returns an array of all packs configured for a given project. Each entry includes `pack_name`, `description`, `token_budget`, and `created_at`. This tool is useful for clients to discover available packs without hardcoding names.

### Strict Budget Mode

When strict_budget is true, the tool returns an error if the pack would exceed its configured token limit. This prevents silent truncation and forces the client to handle budget constraints explicitly.

### Soft Budget Mode

When strict_budget is false, the tool truncates results to stay under the limit, returning as much content as possible while respecting the budget. Truncation is logged and warnings are returned in the response metadata.

## Error Handling

The API returns `INVALID_REQUEST` for unknown pack names and `BUDGET_EXCEEDED` when strict mode is enabled and the pack exceeds its limit. See [[token-budgets]], [[retrieval-tools]], and [[error-codes]] for more information.
