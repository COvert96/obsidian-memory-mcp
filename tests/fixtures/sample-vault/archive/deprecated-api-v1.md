---
tags: [archive, api]
type: note
status: deprecated
---
# Deprecated API v1

API v1 is deprecated as of 2026-01-01 and is no longer maintained. New code should use API v2. This document describes the old API and how to migrate.

## Overview

API v1 provided a simple REST interface for vault operations. It was limited to single-file operations and lacked conflict detection. API v2 introduced multi-file changesets, improved error handling, and standardized response formats.

## Deprecated Endpoints

The following endpoints are deprecated and will be removed on 2026-12-31:

- `POST /propose` (use `/propose-memory-update`)
- `POST /approve` (use `/approve-reject-proposal` with approve=true)
- `POST /reject` (use `/approve-reject-proposal` with approve=false)
- `GET /search` (use `/search-notes`)

Support for v1 endpoints is limited to critical bugfixes only. No new features will be added to v1.

## Migration Path

To migrate from v1: update endpoint URLs, map request/response fields, and test against v2 API. The v1 request body `{"file_path": "...", "content": "..."}` maps to v2 request with explicit `operation` field (create/update/delete). Response format changed from `{"success": true}` to `{"proposal_id": "..."}`. See [[retrieval-tools]] and the v2 documentation for complete migration guidance.
