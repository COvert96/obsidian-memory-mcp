from __future__ import annotations

import argparse
import math
import re
from pathlib import Path


TOKEN_FRAGMENT_PATTERN = re.compile(r"[A-Za-z0-9_/-]+|[^\w\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    """Estimate tokens deterministically for markdown-heavy text.

    The heuristic counts word-like fragments in four-character chunks and counts
    punctuation and markdown markers as one token each. Newlines are normalized so
    Windows and POSIX line endings produce identical counts.
    """

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    token_count = 0
    for fragment in TOKEN_FRAGMENT_PATTERN.findall(normalized):
        if fragment.isalnum() or any(character.isalnum() for character in fragment):
            token_count += math.ceil(len(fragment) / 4)
        else:
            token_count += 1
    return token_count


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Estimate Obsidian Memory MCP token counts.")
    parser.add_argument("--text", help="Inline text to estimate.")
    parser.add_argument("--file", type=Path, help="Path to a text file to estimate.")
    return parser


def main() -> int:
    parser = _build_argument_parser()
    arguments = parser.parse_args()

    if arguments.text is None and arguments.file is None:
        parser.error("Either --text or --file is required.")

    if arguments.file is not None:
        text = arguments.file.read_text(encoding="utf-8")
    else:
        text = arguments.text or ""

    print(estimate_tokens(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())