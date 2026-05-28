---
tags: [api, errors, reference]
type: reference
---
# Error Codes

All API endpoints return structured error responses with a machine-readable error code, a human-readable message, and optional metadata. Understanding error codes is essential for building robust clients that handle failures gracefully.

## Overview

Error responses follow a standard format: `{"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}`. The error code is stable across API versions and should be used for programmatic error handling. The message may change between versions and is intended for debugging.

## Error Response Format

HTTP status codes align with error severity: 400-level codes indicate client errors that will not resolve without user intervention, while 500-level codes indicate transient server errors suitable for retry. The response body always includes the error code, allowing clients to handle errors without parsing the message string.

### Request Errors

Client request errors include `INVALID_REQUEST` (malformed input, missing fields), `INVALID_OPERATION` (operation not supported), and `SCHEMA_VALIDATION_FAILED` (data does not match expected schema). These are typically HTTP 400 Bad Request responses.

### Access Errors

Access control errors include `OUT_OF_BOUNDS` (path outside vault boundaries), `ACCESS_DENIED` (insufficient permissions), and `NOT_FOUND` (requested resource does not exist). These are HTTP 403 Forbidden or 404 Not Found responses.

### State Errors

State-related errors include `CONFLICT` (concurrent modification detected), `ALREADY_EXISTS` (resource already created), and `EXPIRED` (proposal or token has expired). These are HTTP 409 Conflict responses.

## Recovery Patterns

For transient errors (HTTP 5xx), implement exponential backoff retry logic. For client errors (HTTP 4xx), log the error and fix the request before retrying. For conflict errors, reload state and resubmit. See [[vault-boundaries]] and [[retrieval-tools]] for examples of error handling in practice.
