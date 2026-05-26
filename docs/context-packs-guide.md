# Context Packs Guide

Context packs are named bundles of markdown files declared in `memory-mcp.yaml`.
They let operators load recurring context in one `get_context_pack` call while
enforcing a deterministic token budget. The default budget is 8000 tokens; a pack
can override it with `token_budget`.

## Example

```yaml
context_packs:
  - name: api-docs
    description: "Public API reference and usage examples"
    paths:
      - wiki/api/**/*.md
    token_budget: 6000

  - name: architecture
    description: "Architecture decisions and system overview"
    paths:
      - docs/architecture/overview.md
      - docs/adr/**/*.md
    sections:
      - Decision
      - Context

  - name: compliance-bundle
    description: "Compliance policy plus reusable API docs"
    paths:
      - docs/compliance/policy.md
    tags_filter:
      - compliance
    include_context_packs:
      - api-docs
```

`paths` are vault-relative. Explicit paths are evaluated in declaration order;
glob matches are sorted lexicographically for stable output. Included packs are
appended after the including pack's own files, and duplicate files keep their
first occurrence.

## Filtering

`sections` matches markdown headings case-insensitively. Matching sections keep
their original markdown content, including nested subsections. If none of the
requested sections are found in a file, the loader includes the full file and
adds a warning.

`tags_filter` checks frontmatter tags only. A file must contain all listed tags
to be included. Tag-filtered files are skipped during loading and reported by
`mcp-memory pack validate`.

## Budgets

Token counts use the Phase 0 deterministic estimator in `obsidian_memory_mcp.tokens`.
This uses `tiktoken` for the configured GPT-4-compatible tokenizer, so counts are
stable across runs. Actual model tokenization can drift when a future model uses
a different tokenizer, so keep production packs below the hard cap rather than
aiming exactly at it.

With `strict_budget=true`, over-budget packs fail with `ERR_CONTEXT_EXCEEDS_BUDGET`.
With `strict_budget=false`, the loader truncates at complete section boundaries.
When the search index is available, truncation keeps the highest-ranked files by
BM25 score from the pack's file set before falling back to declaration order.

## CLI

```powershell
mcp-memory pack list {vault_path}
mcp-memory pack validate {pack_name} {vault_path}
mcp-memory pack load {pack_name} {vault_path}
```

The vault path is optional when running the command from the vault root. Pack
validation reports included files, missing files, stale files, tag-filtered
files, warnings, token count, and duration.
