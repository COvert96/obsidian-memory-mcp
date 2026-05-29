---
tags: [api, writes, errors]
---
# Conflict Detection

## Hash Mismatch

`update_memory` and `update_note` accept optional `expected_hash` from the most recent `read_note`. When the on-disk `content_hash` differs, the server returns `ERR_HASH_MISMATCH` and performs no write.

## Recovery

1. Call `read_note` for the current hash.
2. Merge or regenerate content.
3. Retry the update with the fresh `expected_hash`.
