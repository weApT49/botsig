"""
Configuration Manager
Loads and validates settings from YAML config file
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Configuration manager with dot-notation access"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "settings.yaml"

        self._config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from YAML file"""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        with open(self._config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value using dot notation
        Example: config.get("broker.name") -> "FBS Cent"
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set config value using dot notation"""
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire config section"""
        return self._config.get(section, {})

    def validate(self) -> bool:
        """Validate required configuration values"""
        required = [
            "broker.name",
            "risk.capital_usc",
            "telegram.bot_token",
            "telegram.chat_id",
        ]

        missing = []
        for key in required:
            if self.get(key) is None:
                missing.append(key)

        if missing:
            raise ValueError(f"Missing required config values: {missing}")

        return True

    def reload(self) -> None:
        """Reload configuration from file"""
        self._load()

    @property
    def raw(self) -> Dict[str, Any]:
        """Get raw configuration dictionary"""
        return self._config.copy()
