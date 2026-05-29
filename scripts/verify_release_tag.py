#!/usr/bin/env python3
"""Verify that a git release tag matches pyproject.toml project.version."""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

from obsidian_memory_mcp.release_metadata import verify_tag_matches_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tag",
        help="Release tag (e.g. v0.2.0-rc.1). Defaults to GITHUB_REF_NAME.",
        nargs="?",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    args = parser.parse_args(argv)

    tag = args.tag
    if tag is None:
        tag = os.environ.get("GITHUB_REF_NAME")
    if not tag:
        print("error: provide tag argument or set GITHUB_REF_NAME", file=sys.stderr)
        return 2

    if not args.pyproject.is_file():
        print(f"error: not found: {args.pyproject}", file=sys.stderr)
        return 1

    pyproject = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    try:
        verify_tag_matches_version(tag, project_version)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"ok: {tag} matches pyproject version {project_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
