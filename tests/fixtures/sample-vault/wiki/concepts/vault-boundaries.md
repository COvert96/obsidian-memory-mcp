---
tags: [concepts, security, guardrails]
type: concept
---
# Vault Boundaries

Vault boundaries are access control rules that prevent clients from reading or writing files outside the configured vault directory. They are enforced through path normalization and guardrail evaluation, ensuring that symlinks, relative paths, and special characters cannot be used to escape the vault.

## What Are Vault Boundaries

Vault boundaries define the directory (and optionally subdirectories) where operations are permitted. By default, all operations must occur within the configured vault root. Additional access policies can grant or deny access to specific subdirectories.

## Path Normalization

All file paths are normalized before evaluation: converted to absolute paths, resolved through symlinks, and checked against the vault root. This prevents bypasses like `../../../etc/passwd` or symlink following. If a normalized path falls outside the vault, an `OUT_OF_BOUNDS` error is returned.

## Access Policies

Access policies are configured in the `memory-mcp.yaml` config file. They consist of allow patterns (which paths clients can access) and deny patterns (which paths to exclude). Policies are evaluated in order — the first matching pattern determines access.

## Guardrail Evaluation

Before any read or write operation, the normalized path is matched against all configured policies. If no allow pattern matches, the operation is denied with `ACCESS_DENIED`. If a deny pattern matches, the operation is denied with `OUT_OF_BOUNDS`. This two-level check provides defense in depth.

## Out-of-Bounds Errors

Operations on paths outside the vault return `OUT_OF_BOUNDS` errors with details about why the path is not allowed. This includes paths above the vault root, paths with invalid characters, and paths explicitly denied by policy. See [[config-schema]], [[error-codes]], and [[vault-boundaries]] for detailed examples.
