---
tags: [operations, setup, runbook]
type: runbook
status: active
---
# Initial Setup

This runbook guides users through setting up a new obsidian-memory vault. It covers prerequisites, installation, configuration, and verification steps.

## Prerequisites

Ensure Python 3.8+ is installed, you have access to a markdown vault directory, and you have git and pip available on your system. SQLite is bundled with Python, so no separate installation is needed.

## Clone and Install

Clone the obsidian-memory repository: `git clone https://github.com/obsidian-memory-mcp/obsidian-memory.git`. Navigate to the directory and install dependencies: `pip install -e .`. Verify installation by running `obsidian-memory --version`.

## Create Vault Config

Create a `memory-mcp.yaml` file in your vault root directory. The file defines access policies and context packs.

### Minimal Config

A minimal config has only required fields: `vault_name` and `access_policies`. Example:

```yaml
vault_name: my-vault
access_policies:
  - type: allow
    pattern: "**"
```

### Config with Context Packs

Add a `context_packs` section to define named collections. Example:

```yaml
context_packs:
  - name: api-docs
    query: "api"
    paths: ["wiki/api/**"]
    token_budget: 3000
```

### Config with Access Policies

Restrict access with deny patterns:

```yaml
access_policies:
  - type: allow
    pattern: "wiki/**"
  - type: deny
    pattern: "**/private/**"
```

## Run Initial Index

Execute `obsidian-memory index` from the vault directory. This scans all markdown files and builds the FTS search index. The first run takes longer than subsequent incremental updates.

## Verify Setup

Test the system with `obsidian-memory search "query"`. Verify results are returned and the index is working. Check [[config-schema]] and [[indexing-pipeline]] for detailed configuration options.
