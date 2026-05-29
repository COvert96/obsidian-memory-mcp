"""Obsidian wikilink parsing and normalization."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

_WIKILINK_RE = re.compile(r"(?P<embed>!?)\[\[(?P<inner>[^\]\n]+)\]\]")


@dataclass(frozen=True)
class WikilinkToken:
    raw: str
    target: str
    alias: str | None


def iter_non_embedded_wikilinks(content: str) -> Iterator[WikilinkToken]:
    for match in _WIKILINK_RE.finditer(content):
        if match.group("embed"):
            continue
        inner = match.group("inner")
        target, alias = parse_wikilink_parts(inner)
        yield WikilinkToken(raw=match.group(0), target=target, alias=alias)


def escape_wikilink_alias_separator(content: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group("embed"):
            return match.group(0)

        inner = match.group("inner")
        delimiter_index = _first_unescaped_pipe(inner)
        if delimiter_index < 0:
            return match.group(0)
        escaped_inner = f"{inner[:delimiter_index]}\\|{inner[delimiter_index + 1 :]}"
        return f"[[{escaped_inner}]]"

    return _WIKILINK_RE.sub(replace, content)


def parse_wikilink_parts(inner: str) -> tuple[str, str | None]:
    unescaped_index = _first_unescaped_pipe(inner)
    if unescaped_index >= 0:
        target = _unescape_pipe(inner[:unescaped_index].strip())
        alias = _unescape_pipe(inner[unescaped_index + 1 :].strip()) or None
        return target, alias

    escaped_index = _first_escaped_pipe(inner)
    if escaped_index < 0:
        return _unescape_pipe(inner.strip()), None

    target_part = inner[:escaped_index]
    if target_part.endswith("\\"):
        target_part = target_part[:-1]
    target = _unescape_pipe(target_part.strip())
    alias = _unescape_pipe(inner[escaped_index + 1 :].strip()) or None
    return target, alias


def _first_unescaped_pipe(value: str) -> int:
    for index, char in enumerate(value):
        if char != "|":
            continue
        if not _is_escaped(value, index):
            return index
    return -1


def _first_escaped_pipe(value: str) -> int:
    for index, char in enumerate(value):
        if char == "|" and _is_escaped(value, index):
            return index
    return -1


def _is_escaped(value: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and value[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _unescape_pipe(value: str) -> str:
    return value.replace("\\|", "|")
