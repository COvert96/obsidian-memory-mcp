You are an expert software engineer who writes clean, well-tested code.

## Context

This is a Python project that uses `uv` as the build backend and package manager.

## Code Implementation

When implementing any code, follow a strict Test-Driven Development (TDD) workflow:

1. Write a failing test first that captures the desired behavior.
2. Write the minimal implementation to make that test pass.
3. Refactor as needed, keeping all tests green.

Prioritize test quality over quantity. A single well-designed test that clearly expresses intent and covers a meaningful case is worth more than many shallow or redundant tests.

## Command Line

- `uv` is the build backend and package manager.
- Always use `uv run` over `.venv/Scripts/python.exe` or `python`.

## Commit Rules
- NEVER add "Co-Authored by ..." in commit messages, PR, or any tracked files.
- Use the `devops` skill when commiting changes.
