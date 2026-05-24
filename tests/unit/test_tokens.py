"""Tests for token estimation (obsidian_memory_mcp.tokens)."""

from __future__ import annotations

import tiktoken

from obsidian_memory_mcp.tokens import estimate_tokens


def test_single_token_words_count_correctly() -> None:
    assert estimate_tokens(" ".join(["x"] * 5)) == 5
    assert estimate_tokens(" ".join(["x"] * 100)) == 100
    assert estimate_tokens(" ".join(["x"] * 1000)) == 1000


def test_line_ending_variants_produce_the_same_count() -> None:
    lf = "# Heading\n\n- bullet\n[[Link]]"
    crlf = "# Heading\r\n\r\n- bullet\r\n[[Link]]"
    assert estimate_tokens(lf) == estimate_tokens(crlf)


def test_estimate_matches_tiktoken_gpt4_encoder() -> None:
    encoder = tiktoken.encoding_for_model("gpt-4")
    text = "# Title\n\n- alpha\n- beta\n\n[[Link]]"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    assert estimate_tokens(text) == len(encoder.encode(normalized, disallowed_special=()))


def test_empty_string_returns_zero() -> None:
    assert estimate_tokens("") == 0
