"""Release tag and changelog helpers for GitHub Actions workflows."""

from __future__ import annotations

import re

_TAG_RC_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)-rc\.(\d+)$")
_TAG_RELEASE_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_CHANGELOG_SECTION_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def tag_to_pep440(tag: str) -> str:
    """Convert a git tag (``v0.2.0-rc.1``) to PEP 440 (``0.2.0rc1``)."""
    normalized = tag.removeprefix("v")
    rc_match = _TAG_RC_PATTERN.fullmatch(normalized)
    if rc_match:
        major, minor, patch, rc_num = rc_match.groups()
        return f"{major}.{minor}.{patch}rc{rc_num}"
    release_match = _TAG_RELEASE_PATTERN.fullmatch(normalized)
    if release_match:
        return normalized
    msg = f"Unsupported release tag format: {tag!r}"
    raise ValueError(msg)


def changelog_version_from_tag(tag: str) -> str:
    """Changelog heading version (``0.2.0-rc.1``) from a git tag."""
    return tag.removeprefix("v")


def extract_changelog_section(changelog_text: str, version: str) -> str:
    """Return markdown body for ``## {version}`` until the next ``##`` heading."""
    headings = list(_CHANGELOG_SECTION_PATTERN.finditer(changelog_text))
    start_index = next(
        (
            match.start()
            for match in headings
            if match.group(1).startswith(version)
        ),
        None,
    )
    if start_index is None:
        msg = f"No changelog section for version {version!r}"
        raise ValueError(msg)

    section_start = changelog_text.find("\n", start_index)
    if section_start == -1:
        msg = f"Changelog section for {version!r} has no body"
        raise ValueError(msg)
    section_start += 1

    following = [
        match.start()
        for match in headings
        if match.start() > start_index
    ]
    section_end = following[0] if following else len(changelog_text)
    body = changelog_text[section_start:section_end].strip()
    if not body:
        msg = f"Changelog section for {version!r} is empty"
        raise ValueError(msg)
    return body


def verify_tag_matches_version(tag: str, project_version: str) -> None:
    """Raise ``ValueError`` when the tag's PEP 440 form differs from ``project_version``."""
    expected = tag_to_pep440(tag)
    if expected != project_version:
        msg = (
            f"Tag {tag!r} maps to PEP 440 {expected!r}, "
            f"but pyproject.toml version is {project_version!r}"
        )
        raise ValueError(msg)
