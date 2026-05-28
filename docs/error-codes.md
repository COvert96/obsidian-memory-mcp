# Error Codes

`src/obsidian_memory_mcp/errors.py` contains the authoritative `ERROR_CATALOG`. Tool documentation should reference these codes instead of redefining independent error semantics.

| Code | Meaning | Recovery |
|---|---|---|
| `ERR_INVALID_REQUEST` | Request payload or query input is invalid. | Check the documented request fields, types, and search syntax. |
| `ERR_INVALID_PROJECT` | The project name is not configured in the server registry. | Use a project key from `memory-mcp-server.yaml`. |
| `ERR_MISSING_FILE` | A requested vault file does not exist. | Verify the vault-relative path and rebuild the index if search results are stale. |
| `ERR_SECTION_NOT_FOUND` | The requested heading was not found in the target note. | Retry with an existing heading from the markdown file. |
| `ERR_FILE_EXISTS` | The target file already exists; cannot overwrite on create. | Verify the path or use the appropriate update tool. |
| `ERR_GUARDRAIL_VIOLATION` | The path or operation violates vault guardrails. | Use an allowed path inside the vault; writes must target `Memory/**` by default. |
| `ERR_HASH_MISMATCH` | The target file changed since it was last read; the supplied `expected_hash` no longer matches the on-disk content. | Call `read_note` to get the current `content_hash`, then retry the update with the updated `expected_hash`. |
| `ERR_STALE_PROPOSAL` | A proposal can no longer be safely applied. | Recreate the proposal against the current file contents. |
| `ERR_CONTEXT_EXCEEDS_BUDGET` | A strict context pack request exceeded its token budget. | Use a smaller pack, adjust the budget, or retry with soft budgeting. |
| `ERR_INTERNAL` | The server hit an unexpected internal failure. | Retry if transient; otherwise inspect logs and file an issue with sanitized details. |

## Handling Pattern

Clients should treat tool errors as recoverable unless the same request repeatedly fails with `ERR_INTERNAL`. For user-correctable errors, present the code, message, and recovery suggestion. Do not include private vault content when reporting failures publicly.
