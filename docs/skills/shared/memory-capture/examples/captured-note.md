---
title: API timeout retry policy
tags: [memory, api, reliability]
created: 2026-05-29
---

# API timeout retry policy

## Summary

Outbound API calls use three retries with exponential backoff (1s, 2s, 4s) and fail closed after the third timeout.

## Details

Decided during incident review: the previous single-retry behavior caused duplicate submissions on slow gateways. Idempotency keys are required on POST endpoints before enabling retries in production.

Related wiki doc: `wiki/api/write-memory-api.md` (reference only; this note is the Memory source of truth).
