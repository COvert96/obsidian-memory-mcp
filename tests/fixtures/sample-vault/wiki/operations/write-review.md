---
tags: [operations, writes, audit]
---
# Write Review

Operators review automated memory changes by reading `write_audit` output and spot-checking affected notes. Because v0.2.0 writes are immediate, review happens after the fact rather than through an approval queue.

## Checklist

1. Run `mcp-memory audit writes` for the vault.
2. Open changed paths under `Memory/**`.
3. Confirm guardrails still match team policy.
