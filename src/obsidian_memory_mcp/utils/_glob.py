"""Vault path glob normalization and regex compilation."""

from __future__ import annotations

import re
from functools import lru_cache


def normalize_glob(pattern: str) -> str:
    return pattern.replace("\\", "/").lstrip("/")


def glob_to_regex(pattern: str) -> str:
    """Convert a normalized vault-relative glob into an anchored regex."""
    pieces: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            pieces.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            pieces.append(".*")
            index += 2
            continue

        character = pattern[index]
        if character == "*":
            pieces.append("[^/]*")
        elif character == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(character))
        index += 1
    pieces.append("$")
    return "".join(pieces)


@lru_cache(maxsize=512)
def compile_glob_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(glob_to_regex(normalize_glob(pattern)))


def glob_matches(pattern: str, vault_path: str) -> bool:
    normalized_path = vault_path.replace("\\", "/").lstrip("/")
    return compile_glob_pattern(pattern).fullmatch(normalized_path) is not None
