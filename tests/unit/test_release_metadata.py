from __future__ import annotations

import pytest

from obsidian_memory_mcp.release_metadata import (
    changelog_version_from_tag,
    extract_changelog_section,
    tag_to_pep440,
    verify_tag_matches_version,
)

SAMPLE_CHANGELOG = """\
# Changelog

## 0.2.0-rc.1 - 2026-05-29

Pre-release notes here.

### Added

- Direct writes.

## 0.1.0 - 2026-05-28

Initial release.
"""


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.2.0-rc.1", "0.2.0rc1"),
        ("v0.2.0", "0.2.0"),
        ("0.2.0-rc.1", "0.2.0rc1"),
    ],
)
def test_tag_to_pep440(tag: str, expected: str) -> None:
    assert tag_to_pep440(tag) == expected


def test_changelog_version_from_tag_strips_v_prefix() -> None:
    assert changelog_version_from_tag("v0.2.0-rc.1") == "0.2.0-rc.1"


def test_extract_changelog_section_returns_body_without_heading() -> None:
    section = extract_changelog_section(SAMPLE_CHANGELOG, "0.2.0-rc.1")
    assert section.startswith("Pre-release notes here.")
    assert "### Added" in section
    assert "0.1.0" not in section


def test_extract_changelog_section_missing_version_raises() -> None:
    with pytest.raises(ValueError, match="No changelog section"):
        extract_changelog_section(SAMPLE_CHANGELOG, "9.9.9")


def test_verify_tag_matches_version_accepts_matching_pep440() -> None:
    verify_tag_matches_version("v0.2.0-rc.1", "0.2.0rc1")


def test_verify_tag_matches_version_rejects_mismatch() -> None:
    with pytest.raises(ValueError, match="pyproject.toml"):
        verify_tag_matches_version("v0.2.0-rc.1", "0.1.0")
