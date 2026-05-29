# OpenAI Codex skills package

Skills for [Codex](https://developers.openai.com/codex/skills): directory + `SKILL.md`, optional `scripts/`, `references/`, `assets/`, and `agents/openai.yaml`.

## Install

Codex discovers skills from `.agents/skills` (repo root and parent paths). Symlink from the repository root:

```powershell
New-Item -ItemType Directory -Force -Path .agents/skills
New-Item -ItemType SymbolicLink -Path .agents/skills/context-bootstrap -Target docs/skills/openai/context-bootstrap
New-Item -ItemType SymbolicLink -Path .agents/skills/memory-capture -Target docs/skills/openai/memory-capture
New-Item -ItemType SymbolicLink -Path .agents/skills/recall-before-answer -Target docs/skills/openai/recall-before-answer
```

User-wide: `$HOME/.agents/skills/<skill-name>/`.

If you copy instead of symlink, merge each `docs/skills/shared/<skill-name>/` tree into the installed skill directory and update links in `SKILL.md` to local filenames.

Restart Codex after adding skills if they do not appear immediately.

## Frontmatter

Codex requires **`name`** and **`description`** on `SKILL.md`. See [Agent Skills](https://developers.openai.com/codex/skills).

| Field | Used in this library | Notes |
|-------|----------------------|-------|
| `name` | Yes | Must match directory name for predictable `$skill` / listing behavior. |
| `description` | Yes | Include when to use, MCP version, and primary tools (progressive disclosure budget). |

Optional per-skill **[agents/openai.yaml](https://developers.openai.com/codex/skills#optional-metadata)** in this package:

| Key | Purpose |
|-----|---------|
| `interface.display_name` | UI label in Codex app |
| `interface.short_description` | Shorter listing text |
| `policy.allow_implicit_invocation` | Default `true`; set `false` to require explicit `$skill` |
| `dependencies.tools` | Declare MCP tool dependency (configure your obsidian-memory-mcp server in Codex MCP settings) |

Codex does not read Claude-only fields (`when_to_use`, `disable-model-invocation`, etc.). Put trigger guidance in `description`.

Workflow steps and MCP parameters are in [shared/](../shared/) `workflow.md` files (not in frontmatter).

## Skills

| Skill | Directory |
|-------|-----------|
| context-bootstrap | [context-bootstrap/](context-bootstrap/) |
| memory-capture | [memory-capture/](memory-capture/) |
| recall-before-answer | [recall-before-answer/](recall-before-answer/) |
