from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from obsidian_memory_mcp.parser import PARSER_VERSION, parse_markdown


def _parse(content: str, *, vault_path: str = "wiki/note.md"):
    return parse_markdown(vault_path=vault_path, content=content)


def test_parser_models_are_immutable() -> None:
    parsed = _parse("# Title\nBody")

    with pytest.raises(FrozenInstanceError):
        parsed.vault_path = "other.md"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("content", "assertion"),
    [
        (
            "---\ntype: concept\n---\n# Title\nBody",
            lambda note: note.frontmatter["type"] == "concept",
        ),
        (
            "---\ntags: [alpha, beta]\n---\n# Title",
            lambda note: note.tags == ("alpha", "beta"),
        ),
        (
            "---\ntags: alpha, beta\n---\n# Title",
            lambda note: note.tags == ("alpha", "beta"),
        ),
        (
            "---\ntags: '#alpha #beta'\n---\n# Title",
            lambda note: note.tags == ("alpha", "beta"),
        ),
        (
            "---\n: broken\n---\n# Title",
            lambda note: note.frontmatter_parse_error is not None,
        ),
        ("no frontmatter\n# Title", lambda note: note.frontmatter == {}),
        ("---\n- not\n- mapping\n---\n# Title", lambda note: note.frontmatter == {}),
        ("# Title\nBody", lambda note: note.headings[0].text == "Title"),
        (
            "# Parent\nA\n## Child\nB",
            lambda note: note.sections[1].section_path == "Parent > Child",
        ),
        (
            "```\n# Not heading\n```\n# Real",
            lambda note: [h.text for h in note.headings] == ["Real"],
        ),
        (
            "~~~\n## Not heading\n~~~\n## Real",
            lambda note: [h.text for h in note.headings] == ["Real"],
        ),
        (
            "# T\nSee [[Other Note]]",
            lambda note: note.wikilinks[0].target == "Other Note",
        ),
        (
            "# T\nSee [[Other Note|alias]]",
            lambda note: note.wikilinks[0].alias == "alias",
        ),
        ("# T\nBody #alpha/sub", lambda note: note.tags == ("alpha/sub",)),
        ("# T\n`#notatag`\n#yes", lambda note: note.tags == ("yes",)),
        (
            "# Repeat\nA\n# Repeat\nB",
            lambda note: [h.ordinal for h in note.headings] == [1, 2],
        ),
        (
            "# Repeat\nA\n# Repeat\nB",
            lambda note: note.sections[1].section_key == "wiki/note.md#repeat#2",
        ),
        (
            "# Title\nBody",
            lambda note: note.blocks[0].block_key == "wiki/note.md#title#1::block-1",
        ),
        (
            "# Title\r\nBody\r\n",
            lambda note: (
                note.normalized_content_hash
                == _parse("# Title\nBody\n").normalized_content_hash
            ),
        ),
        (
            "# Title\r\nBody\r\n",
            lambda note: (
                note.raw_content_hash != _parse("# Title\nBody\n").raw_content_hash
            ),
        ),
        ("# Title\n\n   \n", lambda note: note.blocks == ()),
        (
            "Body without heading",
            lambda note: note.sections[0].section_key == "wiki/note.md#root#1",
        ),
        ("# Title ###\nBody", lambda note: note.headings[0].text == "Title"),
        (
            "# Hello, World!\nA\n# Hello World\nB",
            lambda note: [h.ordinal for h in note.headings] == [1, 2],
        ),
        (
            "# T\n| A | B |\n| - | - |\n| 1 | 2 |",
            lambda note: (
                len(note.blocks) == 1 and "| 1 | 2 |" in note.blocks[0].content
            ),
        ),
        (
            "# T\n```python\nprint('x')\n```",
            lambda note: (
                len(note.blocks) == 1 and "```python" in note.blocks[0].content
            ),
        ),
        (
            "# T\n"
            + "\n\n".join(f"paragraph {i} " + ("word " * 80) for i in range(20)),
            lambda note: len(note.blocks) > 1,
        ),
        (
            "# T\n" + ("word " * 5000),
            lambda note: all(
                block.token_count_estimate <= 1000 for block in note.blocks
            ),
        ),
        (
            "---\ntags: [front]\n---\n# T\nBody #inline",
            lambda note: note.blocks[0].tags == ("front", "inline"),
        ),
        ("# T\nBody", lambda note: note.parser_version == PARSER_VERSION),
        (
            "# T\n![[embedded.png]] and [[Note#Heading]]",
            lambda note: [link.target for link in note.wikilinks] == ["Note#Heading"],
        ),
    ],
)
def test_parser_covers_markdown_scenarios(content: str, assertion) -> None:
    assert assertion(_parse(content))


def test_block_segmentation_is_deterministic_and_non_overlapping() -> None:
    content = "# T\n" + "\n\n".join(
        f"paragraph {index} " + ("word " * 90) for index in range(12)
    )

    first = _parse(content)
    second = _parse(content)

    assert [block.block_key for block in first.blocks] == [
        block.block_key for block in second.blocks
    ]
    assert [block.content for block in first.blocks] == [
        block.content for block in second.blocks
    ]
    assert len(first.blocks) == len(set(block.content for block in first.blocks))


def test_pipe_in_prose_does_not_split_paragraph_as_table() -> None:
    parsed = _parse(
        "# Title\n"
        "First prose line\n"
        "Option A | Option B are both valid approaches.\n"
        "Final prose line"
    )

    assert parsed.blocks[0].content == (
        "First prose line\n"
        "Option A | Option B are both valid approaches.\n"
        "Final prose line"
    )


def test_raw_and_normalized_hashes_accept_bytes_input() -> None:
    parsed = parse_markdown(vault_path="wiki/bytes.md", content=b"# Bytes\r\nBody\r\n")

    assert parsed.raw_content_hash
    assert (
        parsed.normalized_content_hash
        == _parse("# Bytes\nBody\n").normalized_content_hash
    )
