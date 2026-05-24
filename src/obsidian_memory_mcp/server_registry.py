"""Server-level project registry: maps project names to vault root directories.

The registry is loaded from a YAML file once at server startup (in the
Composition Root — `create_mcp_server`) and passed as a dependency to each
tool implementation.  This module contains only pure, stateless functions;
there is no module-level cache or global mutable state.

Registry file format::

    projects:
      my-project: /absolute/path/to/vault
      another:    /absolute/path/to/another-vault
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


SERVER_REGISTRY_ENV_VAR = "OBSIDIAN_MEMORY_MCP_REGISTRY"
DEFAULT_SERVER_REGISTRY_FILE = "memory-mcp-server.yaml"


@dataclass(frozen=True)
class ProjectRegistry:
    """Immutable mapping of project names to resolved vault root paths."""

    projects: MappingProxyType[str, Path]

    def resolve(self, project: str) -> Path:
        """Return the vault root for *project*, or raise `ToolExecutionError`.

        Raises:
            ToolExecutionError: with `ERR_INVALID_PROJECT` when the project
                name is not present in the registry.
        """
        vault_root = self.projects.get(project)
        if vault_root is not None:
            return vault_root

        known = ", ".join(sorted(self.projects)) or "<none>"
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_INVALID_PROJECT,
                message=f"Project '{project}' is not configured in the server registry.",
                details={
                    "project": project,
                    "known_projects": sorted(self.projects),
                    "suggestion": (
                        f"Use one of the configured projects: {known}, "
                        f"or update {DEFAULT_SERVER_REGISTRY_FILE}."
                    ),
                },
            )
        )


def load_project_registry(registry_path: str | Path | None = None) -> ProjectRegistry:
    """Load and validate the server registry file, returning a `ProjectRegistry`.

    Resolution order for the registry file path:
    1. The explicit *registry_path* argument.
    2. The ``OBSIDIAN_MEMORY_MCP_REGISTRY`` environment variable.
    3. ``memory-mcp-server.yaml`` in the current working directory.

    Raises:
        ToolExecutionError: with `ERR_INVALID_PROJECT` when the file is
            missing, contains invalid YAML, or fails structural validation.
    """
    resolved_path = _resolve_registry_path(registry_path)
    return _load_registry_file(resolved_path)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_registry_path(registry_path: str | Path | None) -> Path:
    if registry_path is not None:
        return Path(registry_path).resolve(strict=False)

    from_env = os.environ.get(SERVER_REGISTRY_ENV_VAR)
    if from_env:
        return Path(from_env).resolve(strict=False)

    return (Path.cwd() / DEFAULT_SERVER_REGISTRY_FILE).resolve(strict=False)


def _load_registry_file(registry_path: Path) -> ProjectRegistry:
    if not registry_path.exists():
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_INVALID_PROJECT,
                message=f"Server registry file not found at '{registry_path}'.",
                details={
                    "registry_path": str(registry_path),
                    "suggestion": (
                        f"Create {DEFAULT_SERVER_REGISTRY_FILE} "
                        f"or set {SERVER_REGISTRY_ENV_VAR} to the correct path."
                    ),
                },
            )
        )

    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_INVALID_PROJECT,
                message=(
                    f"Server registry file '{registry_path}' contains malformed YAML: {exc}."
                ),
                details={
                    "registry_path": str(registry_path),
                    "suggestion": "Fix the YAML syntax and restart the MCP server.",
                },
            )
        ) from exc

    projects = _parse_projects(raw, registry_path)
    return ProjectRegistry(projects=MappingProxyType(projects))


def _parse_projects(raw: Any, registry_path: Path) -> dict[str, Path]:
    if not isinstance(raw, dict):
        raise _format_error(registry_path, "a top-level YAML mapping with a 'projects' key")

    projects_raw = raw.get("projects")
    if not isinstance(projects_raw, dict) or not projects_raw:
        raise _format_error(registry_path, "a 'projects' mapping with at least one entry")

    result: dict[str, Path] = {}
    for name, value in projects_raw.items():
        if not isinstance(name, str) or not name:
            raise _format_error(registry_path, "non-empty string project names")

        if not isinstance(value, str):
            raise _format_error(
                registry_path,
                "absolute path strings as project values "
                "(e.g. `my-project: /absolute/path/to/vault`)",
            )

        vault_path = Path(value)
        if not vault_path.is_absolute():
            raise _format_error(registry_path, "absolute vault paths for all projects")

        resolved = vault_path.resolve(strict=False)
        if not resolved.is_dir():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_INVALID_PROJECT,
                    message=(
                        f"Project '{name}' points to '{resolved}', "
                        "which is not an existing directory."
                    ),
                    details={
                        "project": name,
                        "vault_path": str(resolved),
                        "suggestion": "Create the vault directory or fix the project mapping.",
                    },
                )
            )

        result[name] = resolved

    return result


def _format_error(registry_path: Path, expected: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(
            ErrorCode.ERR_INVALID_PROJECT,
            message=f"Server registry file '{registry_path}' is invalid.",
            details={
                "registry_path": str(registry_path),
                "expected": expected,
                "suggestion": (
                    "Use the format:\n"
                    "  projects:\n"
                    "    project-name: /absolute/path/to/vault"
                ),
            },
        )
    )
