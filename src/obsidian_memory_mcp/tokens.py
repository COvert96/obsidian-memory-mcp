from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path

import tiktoken

DEFAULT_TOKEN_MODEL = "gpt-4"


def estimate_tokens(text: str) -> int:
    """Estimate token count with the GPT-4 tokenizer via tiktoken.

    Line endings are normalized so LF and CRLF inputs produce identical counts.
    """

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return len(_encoder().encode(normalized, disallowed_special=()))


@lru_cache(maxsize=1)
def _encoder() -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(DEFAULT_TOKEN_MODEL)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate Obsidian Memory MCP token counts."
    )
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
