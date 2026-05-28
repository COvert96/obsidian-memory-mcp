from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path


def test_installed_package_version_comes_from_project_metadata() -> None:
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    expected = pyproject_data["project"]["version"]
    assert version("obsidian-memory-mcp") == expected
