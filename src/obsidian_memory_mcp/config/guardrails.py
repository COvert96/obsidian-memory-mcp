from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from obsidian_memory_mcp.config.model import AccessPolicy, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.paths import normalize_vault_path


class GuardrailEvaluator:
    def __init__(self, config: ProjectConfig):
        self._config = config
        self._read_policy = _CompiledPolicy(config.write_constraints.read)
        self._write_policy = _CompiledPolicy(config.write_constraints.write)
        self._normalized_paths: dict[str, Path] = {}

    def check_read(self, requested_path: str | Path) -> Path:
        return self._resolve_allowed_path("read", requested_path, self._read_policy)

    def allows_read_relative(self, relative_path: str | Path) -> bool:
        normalized = str(relative_path).replace("\\", "/").lstrip("/")
        return self._read_policy.evaluate(normalized).allowed

    def check_write(self, requested_path: str | Path) -> Path:
        return self._resolve_allowed_path("write", requested_path, self._write_policy)

    def _resolve_allowed_path(
        self,
        operation: str,
        requested_path: str | Path,
        policy: "_CompiledPolicy",
    ) -> Path:
        resolved_path = self._normalize_requested_path(requested_path)
        relative_path = resolved_path.relative_to(self._config.vault_path).as_posix()
        decision = policy.evaluate(relative_path)
        if decision.allowed:
            return resolved_path

        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_GUARDRAIL_VIOLATION,
                message=(
                    f"Path '{relative_path}' violates {operation} {decision.reason} "
                    f"constraint '{decision.pattern}'."
                ),
                details={
                    "operation": operation,
                    "path": relative_path,
                    "constraint": decision.pattern,
                    "suggestion": f"Update write_constraints.{operation}.allow or choose an allowed path.",
                },
            )
        )

    def _normalize_requested_path(self, requested_path: str | Path) -> Path:
        cache_key = str(requested_path)
        if cache_key not in self._normalized_paths:
            self._normalized_paths[cache_key] = normalize_vault_path(
                self._config.vault_path,
                requested_path,
            )
        return self._normalized_paths[cache_key]


@dataclass(frozen=True)
class _GuardrailDecision:
    allowed: bool
    reason: str
    pattern: str


@dataclass(frozen=True)
class _CompiledRule:
    raw_pattern: str
    regex: re.Pattern[str]

    def matches(self, relative_path: str) -> bool:
        return bool(self.regex.fullmatch(relative_path))


class _CompiledPolicy:
    def __init__(self, policy: AccessPolicy):
        self._allow = tuple(_compile_rule(pattern) for pattern in policy.allow)
        self._deny = tuple(_compile_rule(pattern) for pattern in policy.deny)

    def evaluate(self, relative_path: str) -> _GuardrailDecision:
        for rule in self._deny:
            if rule.matches(relative_path):
                return _GuardrailDecision(False, "deny", rule.raw_pattern)

        for rule in self._allow:
            if rule.matches(relative_path):
                return _GuardrailDecision(True, "allow", rule.raw_pattern)

        return _GuardrailDecision(False, "allow", "<default deny>")


def _compile_rule(pattern: str) -> _CompiledRule:
    normalized = pattern.replace("\\", "/").lstrip("/")
    if normalized.endswith("/"):
        directory = re.escape(normalized.rstrip("/"))
        return _CompiledRule(pattern, re.compile(rf"{directory}(/.*)?"))

    if not any(character in normalized for character in "*?[]"):
        return _CompiledRule(pattern, re.compile(re.escape(normalized)))

    return _CompiledRule(pattern, re.compile(_glob_to_regex(normalized)))


def _glob_to_regex(pattern: str) -> str:
    pieces: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                if index + 2 < len(pattern) and pattern[index + 2] == "/":
                    pieces.append("(?:.*/)?")
                    index += 3
                else:
                    pieces.append(".*")
                    index += 2
            else:
                pieces.append("[^/]*")
                index += 1
        elif character == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(character))
            index += 1
    pieces.append("$")
    return "".join(pieces)
