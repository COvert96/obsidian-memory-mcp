# Agent Skills Library

Published MCP-focused agent skills for **obsidian-memory-mcp** (>= v0.2.0). Five skills teach agents how to bootstrap context, capture and maintain memory, recall vault notes, and format well-structured `Memory/` files using direct-write tools — no proposal tools.

This library is split by **provider** (authoring format and install path) and **shared** artifacts (workflows, templates, examples, scripts).

```
docs/skills/
├── README.md                 # This file
├── shared/<skill-name>/      # Provider-neutral workflow + artifacts
│   ├── workflow.md           # MCP tool sequences (canonical logic)
│   ├── template.md           # Optional scaffolds
│   ├── examples/
│   └── scripts/              # memory-capture only
├── claude/<skill-name>/      # Claude Code SKILL.md + frontmatter
│   └── SKILL.md
└── openai/<skill-name>/      # Codex SKILL.md + optional agents/openai.yaml
    ├── SKILL.md
    └── agents/openai.yaml
```

| Package | Install location | Documentation |
|---------|------------------|---------------|
| [claude/](claude/) | `.claude/skills/<skill-name>/` or `~/.claude/skills/` | [Claude Code skills](https://code.claude.com/docs/en/skills) |
| [openai/](openai/) | `.agents/skills/<skill-name>/` or `~/.agents/skills/` | [Codex Agent Skills](https://developers.openai.com/codex/skills) |
| [shared/](shared/) | Referenced via relative links from provider `SKILL.md` | MCP workflows only |

Repo-local tooling skills under `.claude/skills/` and `.agents/skills/` (devops, PRD, etc.) stay separate from this published library.

## Quick install (repository root)

**Claude Code** — symlink provider entrypoints (keeps `shared/` paths valid):

```powershell
New-Item -ItemType Directory -Force -Path .claude/skills
foreach ($s in 'context-bootstrap','memory-capture','recall-before-answer','memory-maintenance','structured-note-template') {
  New-Item -ItemType SymbolicLink -Force -Path ".claude/skills/$s" -Target "docs/skills/claude/$s"
}
```

**Codex** — symlink into `.agents/skills`:

```powershell
New-Item -ItemType Directory -Force -Path .agents/skills
foreach ($s in 'context-bootstrap','memory-capture','recall-before-answer','memory-maintenance','structured-note-template') {
  New-Item -ItemType SymbolicLink -Force -Path ".agents/skills/$s" -Target "docs/skills/openai/$s"
}
```

If you copy files elsewhere, merge each `shared/<skill-name>/` directory into the installed skill folder and fix links in `SKILL.md`.

## Provider frontmatter comparison

Both providers use `SKILL.md` with YAML frontmatter. **Only use fields each platform documents** — unknown keys are ignored or may confuse tooling.

### Claude Code ([full reference](https://code.claude.com/docs/en/skills#frontmatter-reference))

| Field | Required | In this library |
|-------|----------|-----------------|
| `description` | Recommended | Yes — include MCP version and tools |
| `name` | No | Yes — matches directory name |
| `when_to_use` | No | Yes — trigger phrases (counts toward 1,536 char listing cap with `description`) |
| `user-invocable` | No | Default true |
| `disable-model-invocation` | No | Default false |
| `allowed-tools`, `disallowed-tools` | No | Not set |
| `argument-hint`, `arguments` | No | Not set |
| `context`, `agent`, `hooks`, `paths`, `model`, `effort`, `shell` | No | Not set |

### OpenAI Codex ([Agent Skills](https://developers.openai.com/codex/skills))

| Field | Required | In this library |
|-------|----------|-----------------|
| `name` | **Yes** | Yes |
| `description` | **Yes** | Yes — include triggers, MCP version, tools |
| `agents/openai.yaml` | No | Optional `interface` + `dependencies.tools` (MCP) per skill |

Codex does **not** use `when_to_use`, `trigger`, `compatible-with`, or `tools-required` as frontmatter — those belong in `description` and [workflow.md](shared/).

### MCP metadata (both providers)

Server version and tool lists are documented in:

- `description` / `when_to_use` (Claude)
- `description` (Codex)
- `shared/<skill>/workflow.md` (canonical tool call sequences)

Requires **obsidian-memory-mcp >= v0.2.0**.

## Shared artifacts

| Artifact | Purpose |
|----------|---------|
| `workflow.md` | Overview, when to use, numbered MCP steps, see also |
| `template.md` | Fill-in scaffolds (`{project}` only as brace placeholder) |
| `examples/` | Sample outputs |
| `scripts/` | `memory-capture` — `validate-note.py` (local YAML check, no network) |

## Available skills

| Skill | Description | MCP tools | Claude | OpenAI | Shared workflow |
|-------|-------------|-----------|--------|--------|-----------------|
| context-bootstrap | Load context pack at session start | `list_context_packs`, `get_context_pack`, `search_notes` | [claude/context-bootstrap/](claude/context-bootstrap/) | [openai/context-bootstrap/](openai/context-bootstrap/) | [shared/context-bootstrap/](shared/context-bootstrap/) |
| memory-capture | Capture insights at conversation end | `search_notes`, `read_note`, `write_memory`, `update_memory` | [claude/memory-capture/](claude/memory-capture/) | [openai/memory-capture/](openai/memory-capture/) | [shared/memory-capture/](shared/memory-capture/) |
| recall-before-answer | Search before answering | `search_notes`, `read_note`, `read_section` | [claude/recall-before-answer/](claude/recall-before-answer/) | [openai/recall-before-answer/](openai/recall-before-answer/) | [shared/recall-before-answer/](shared/recall-before-answer/) |
| memory-maintenance | Periodically triage stale or `#review` memory notes | `search_notes`, `read_note`, `update_memory` | [claude/memory-maintenance/](claude/memory-maintenance/) | [openai/memory-maintenance/](openai/memory-maintenance/) | [shared/memory-maintenance/](shared/memory-maintenance/) |
| structured-note-template | Frontmatter and heading conventions for `Memory/` notes | none | [claude/structured-note-template/](claude/structured-note-template/) | [openai/structured-note-template/](openai/structured-note-template/) | [shared/structured-note-template/](shared/structured-note-template/) |

## Validate memory notes

From repository root:

```powershell
uv run python docs/skills/shared/memory-capture/scripts/validate-note.py docs/skills/shared/memory-capture/examples/captured-note.md
```

## Related documentation

- [Tool reference](../tool-reference.md)
- [Context packs guide](../context-packs-guide.md)
- [Write tools guide](../write-tools-guide.md)
- [Retrieval guide](../retrieval-guide.md)
