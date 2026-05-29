#!/usr/bin/env python3
"""Extract a CHANGELOG.md section for a release tag into a GitHub release notes file.

The release workflow uses this to populate the GitHub Release body from CHANGELOG.md
instead of writing notes by hand in the GitHub UI.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from obsidian_memory_mcp.release_metadata import (
    changelog_version_from_tag,
    extract_changelog_section,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tag",
        nargs="?",
        help="Release tag (e.g. v0.2.0-rc.1). Defaults to GITHUB_REF_NAME.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to CHANGELOG.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("release-notes.md"),
        help="File to write (default: release-notes.md)",
    )
    args = parser.parse_args(argv)

    tag = args.tag
    if tag is None:
        tag = os.environ.get("GITHUB_REF_NAME")
    if not tag:
        print("error: provide tag argument or set GITHUB_REF_NAME", file=sys.stderr)
        return 2

    if not args.changelog.is_file():
        print(f"error: not found: {args.changelog}", file=sys.stderr)
        return 1

    version = changelog_version_from_tag(tag)
    changelog_text = args.changelog.read_text(encoding="utf-8")
    try:
        body = extract_changelog_section(changelog_text, version)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    args.output.write_text(body + "\n", encoding="utf-8")
    print(f"wrote {args.output} for {version} ({tag})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
