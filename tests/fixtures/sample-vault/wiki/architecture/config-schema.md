---
tags: [architecture, config]
type: reference
---
# Config Schema

The vault configuration is defined in `memory-mcp.yaml`, a YAML file at the vault root that specifies access policies, context packs, and indexing behavior. This document describes the schema and validation rules.

## File Location

The config file must be named `memory-mcp.yaml` and located at the vault root directory (the directory passed to the MCP server). If the file is missing, the server initializes with defaults and logs a warning.

## Top-Level Fields

The config file contains: `vault_name` (string, required), `owner` (string, optional), `access_policies` (array, required), `context_packs` (array, optional), `indexing` (object, optional), and `retention` (object, optional). Additional fields are ignored for forward compatibility.

## Access Policy Config

Access policies define which directories clients can read from and write to. Each policy has `type` (either `allow` or `deny`), `pattern` (glob pattern), and optional `tags` (array of tags that must match). Policies are evaluated in order.

### Allow Patterns

Allow patterns grant read or write access to matching paths. Multiple allow patterns can be specified. Access is granted if any allow pattern matches. For example, `pattern: wiki/**` allows access to all files under wiki/.

### Deny Patterns

Deny patterns revoke access for matching paths, overriding allow patterns. A common pattern is `pattern: "**/private/**"` to deny access to private directories. Deny patterns are evaluated after allow patterns.

### Evaluation Order

Policies are evaluated in the order they appear in the config. The first matching policy determines access. A best practice is to place specific deny patterns before general allow patterns.

## Context Pack Config

Context packs are named collections of search results configured in the `context_packs` array. Each pack has `name` (string), `description` (string), `query` (FTS query string), `paths` (array of include patterns), `token_budget` (number), and optional `tags` (array of required tags). Packs are retrieved by name using the Context Pack API.

## Validation Rules

The schema is validated when the server starts. Missing required fields are reported as errors and prevent startup. Malformed YAML or invalid regex patterns are also reported. Path patterns must be valid glob expressions. See [[vault-boundaries]] and [[initial-setup]] for configuration examples.
