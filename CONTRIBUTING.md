# Contributing

## Local Setup

```powershell
git clone https://github.com/COvert96/obsidian-memory-mcp.git
cd obsidian-memory-mcp
uv sync --group dev
uv run pytest tests
```

Use `uv run` for project commands. Do not call `.venv/Scripts/python.exe` or bare `python` for repository workflows.

## Required Checks

```powershell
uv run ruff check
uv run mypy --strict src
uv run python scripts/radon_gate.py
uv run pytest tests
uv run pytest tests/release
```

Radon fails the gate when any module has cyclomatic complexity grade **C+**, maintainability index grade **C**, or maintainability index below **20**. See [docs/python-api.md](docs/python-api.md) for intended import boundaries.

Coverage target for release-critical code is 80%. CI generates `coverage.xml` and terminal coverage output.

## TDD Expectations

Use a TDD approach for code changes. Add or update one focused test that captures the behavior before changing production code. One good test is better than broad brittle coverage.

## Pull Requests

- Keep changes focused on one behavior or documentation goal.
- Include tests for behavior changes and explain any intentional coverage gaps.
- Update docs and benchmark expected results when fixture content or public behavior changes.
- Do not include real private vault data, credentials, or personal notes.

## Agent Instructions

Repository-specific agent instructions live in [AGENTS.md](AGENTS.md). They are retained and linked here for contributors using coding agents.
