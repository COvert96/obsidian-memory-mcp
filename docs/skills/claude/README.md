# Claude Code skills package

Skills for [Claude Code](https://code.claude.com/docs/en/skills) following the [Agent Skills](https://agentskills.io) layout: each skill is a directory with `SKILL.md` plus optional supporting files.

## Install

From the repository root, symlink (recommended) so paths to `shared/` keep working:

```powershell
New-Item -ItemType Directory -Force -Path .claude/skills
New-Item -ItemType SymbolicLink -Path .claude/skills/context-bootstrap -Target docs/skills/claude/context-bootstrap
New-Item -ItemType SymbolicLink -Path .claude/skills/memory-capture -Target docs/skills/claude/memory-capture
New-Item -ItemType SymbolicLink -Path .claude/skills/recall-before-answer -Target docs/skills/claude/recall-before-answer
```

Or copy `docs/skills/claude/<skill-name>/` to `.claude/skills/<skill-name>/` **and** copy `docs/skills/shared/<skill-name>/` into the same directory (merge `workflow.md`, `template.md`, `examples/`, `scripts/`).

Personal skills: `~/.claude/skills/<skill-name>/` (same layout).

## Frontmatter

Claude uses YAML frontmatter on `SKILL.md`. See the [frontmatter reference](https://code.claude.com/docs/en/skills#frontmatter-reference) for all fields.

| Field | Used in this library | Notes |
|-------|----------------------|-------|
| `name` | Yes | Display name; command is the **directory name** (`/context-bootstrap`). |
| `description` | Yes | Required for discovery; include MCP version and tool names. |
| `when_to_use` | Yes | Trigger phrases; appended to description in listings (1,536 char cap combined). |
| `user-invocable` | Default `true` | Set `false` for background-only skills. |
| `disable-model-invocation` | Default `false` | Set `true` for manual-only workflows. |
| `allowed-tools` | No | Optional; pre-approve MCP/bash tools per skill. |
| `argument-hint`, `arguments` | No | For parameterized `/skill` invocations. |
| `context`, `agent` | No | Subagent execution. |
| `paths` | No | Auto-activate when editing matching files. |

MCP-specific requirements (tool list, server version) live in `description` / `when_to_use` and in [shared workflow files](../shared/).

## Skills

| Skill | Directory |
|-------|-----------|
| context-bootstrap | [context-bootstrap/](context-bootstrap/) |
| memory-capture | [memory-capture/](memory-capture/) |
| recall-before-answer | [recall-before-answer/](recall-before-answer/) |
