---
tags: [operations, troubleshooting]
type: runbook
---
# Troubleshooting Guide

This guide covers common errors, their causes, and solutions. Start with the error category that matches your issue.

## Config Errors

### File Not Found

The `memory-mcp.yaml` file is missing or the path is incorrect. Solution: Create the file in the vault root directory. Use [[initial-setup]] as a template.

### Invalid YAML

The config file has syntax errors (bad indentation, quotes, colons). Solution: Validate the YAML with an online validator. Common mistakes: mixing tabs and spaces, forgetting quotes around strings with special characters.

### Missing Required Fields

Required fields `vault_name` and `access_policies` are missing. Solution: Add these fields to your config. See [[config-schema]] for the complete schema.

## Indexing Failures

The index command exits with an error. Check the error message: "Permission denied" means the vault directory is not readable; try running with `sudo`. "Disk full" means the drive needs space. "Corrupted database" requires `--full-rebuild`.

## Search Problems

See [[search-debugging]] for detailed troubleshooting. Quick checks: verify the index is recent with `obsidian-memory index --status`, try simpler queries, and check path filters are correct.

## MCP Startup Issues

### Port Already in Use

The server port (default 3000) is already in use. Solution: Use `--port <number>` to specify a different port, or kill the existing server with `lsof -i :3000 | awk 'NR==2 {print $2}' | xargs kill -9`.

### Server Registry Not Found

The MCP server registry is not configured. Solution: Check that the server is registered in your MCP client's configuration. For Claude Code, see the update-config skill.

## Guardrail Violations

Operations return `OUT_OF_BOUNDS` errors. This means the requested path is outside the allowed vault directory or explicitly denied by policy. Solution: Check [[vault-boundaries]] and [[config-schema]] to verify your access policies are correct.
