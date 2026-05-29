"""Cross-cutting helpers with no domain policy."""

from obsidian_memory_mcp.utils._glob import (
    compile_glob_pattern,
    glob_matches,
    glob_to_regex,
    normalize_glob,
)
from obsidian_memory_mcp.utils._hashing import sha256_bytes, sha256_file
from obsidian_memory_mcp.utils._paths import normalize_vault_path
from obsidian_memory_mcp.utils._time import duration_ms
from obsidian_memory_mcp.utils._wikilinks import (
    WikilinkToken,
    escape_wikilink_alias_separator,
    iter_non_embedded_wikilinks,
    parse_wikilink_parts,
)

__all__ = [
    "WikilinkToken",
    "compile_glob_pattern",
    "duration_ms",
    "escape_wikilink_alias_separator",
    "glob_matches",
    "glob_to_regex",
    "iter_non_embedded_wikilinks",
    "normalize_glob",
    "normalize_vault_path",
    "parse_wikilink_parts",
    "sha256_bytes",
    "sha256_file",
]
