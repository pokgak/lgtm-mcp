"""Configuration loading with environment variable expansion."""

import os
import re
from pathlib import Path
from typing import Any

import yaml

from lgtm_mcp.models.config import LGTMConfig

DEFAULT_CONFIG_PATHS = [
    Path.home() / ".config" / "lgtm-mcp" / "config.yaml",
    Path.home() / ".config" / "lgtm-mcp" / "config.yml",
    Path("config.yaml"),
    Path("config.yml"),
]

ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in config values.

    Supports ${VAR_NAME} syntax. If the variable is not set, the placeholder
    is replaced with an empty string.
    """
    if isinstance(value, str):

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        expanded = ENV_VAR_PATTERN.sub(replace_var, value)
        return expanded if expanded else None
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def find_config_path() -> Path | None:
    """Find the config file path."""
    env_path = os.environ.get("LGTM_MCP_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"Config file not found at LGTM_MCP_CONFIG path: {env_path}")

    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path

    return None


def load_config(config_path: Path | str | None = None) -> LGTMConfig:
    """Load and validate the configuration.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Validated LGTMConfig instance

    Raises:
        FileNotFoundError: If no config file is found
        ValueError: If config validation fails
    """
    path = Path(config_path) if config_path else find_config_path()

    if path is None:
        raise FileNotFoundError(
            "No config file found. Create one at ~/.config/lgtm-mcp/config.yaml "
            "or set LGTM_MCP_CONFIG environment variable."
        )

    with open(path) as f:
        raw_config = yaml.safe_load(f)

    expanded_config = expand_env_vars(raw_config)

    return LGTMConfig.model_validate(expanded_config)


class InstanceManager:
    """Manages LGTM instances and provides access to clients."""

    def __init__(self, config: LGTMConfig):
        self.config = config
        self._current_default: str = config.default_instance

    @property
    def default_instance(self) -> str:
        """Get the current default instance name."""
        return self._current_default

    def set_default(self, instance: str) -> None:
        """Set the default instance for this session."""
        if instance not in self.config.instances:
            raise ValueError(f"Unknown instance: {instance}")
        self._current_default = instance

    def list_instances(self) -> list[dict[str, Any]]:
        """List all configured instances with their backends."""
        result = []
        for name, instance in self.config.instances.items():
            info = {
                "name": name,
                "is_default": name == self._current_default,
                "backends": {
                    "loki": instance.loki.url if instance.loki else None,
                    "prometheus": instance.prometheus.url if instance.prometheus else None,
                    "tempo": instance.tempo.url if instance.tempo else None,
                },
            }
            result.append(info)
        return result

    def get_instance(self, name: str | None = None) -> str:
        """Resolve instance name, using default if not specified."""
        return name or self._current_default


_instance_manager: InstanceManager | None = None


def get_instance_manager(config: LGTMConfig | None = None) -> InstanceManager:
    """Get or create the global instance manager."""
    global _instance_manager
    if _instance_manager is None:
        if config is None:
            config = load_config()
        _instance_manager = InstanceManager(config)
    return _instance_manager


def reset_instance_manager() -> None:
    """Reset the global instance manager (for testing)."""
    global _instance_manager
    _instance_manager = None
