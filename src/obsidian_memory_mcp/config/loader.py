from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from obsidian_memory_mcp.config.model import CONFIG_FILE_NAME, ProjectConfig
from obsidian_memory_mcp.config.validator import ConfigValidationException, ConfigValidator
from obsidian_memory_mcp.errors import ErrorCode, build_error


class ConfigLoader:
    def __init__(self, vault_root: str | Path, validator: ConfigValidator | None = None):
        self._vault_root = Path(vault_root)
        self._validator = validator or ConfigValidator()
        self._cached_config: ProjectConfig | None = None

    def load(self) -> ProjectConfig:
        if self._cached_config is not None:
            return self._cached_config

        config_path = self._vault_root / CONFIG_FILE_NAME
        if not config_path.exists():
            raise ConfigValidationException(
                build_error(
                    ErrorCode.ERR_INVALID_PROJECT,
                    message=f"Config file not found at '{config_path}'.",
                    details={
                        "field": CONFIG_FILE_NAME,
                        "suggestion": f"Create {CONFIG_FILE_NAME} in the vault root and retry.",
                    },
                )
            )

        loaded_data = self._read_yaml(config_path)
        self._cached_config = self._validator.validate(loaded_data)
        return self._cached_config

    @staticmethod
    def _read_yaml(config_path: Path) -> Any:
        try:
            return yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise ConfigValidationException(
                build_error(
                    ErrorCode.ERR_INVALID_PROJECT,
                    message=f"Config file '{config_path}' contains malformed YAML: {error}.",
                    details={
                        "field": CONFIG_FILE_NAME,
                        "suggestion": "Fix the YAML syntax, then run 'mcp-memory config validate' again.",
                    },
                )
            ) from error


_LOADERS_BY_VAULT_ROOT: dict[Path, ConfigLoader] = {}


def load_project_config(vault_root: str | Path) -> ProjectConfig:
    resolved_vault_root = Path(vault_root).resolve(strict=False)
    loader = _LOADERS_BY_VAULT_ROOT.setdefault(resolved_vault_root, ConfigLoader(resolved_vault_root))
    return loader.load()
