"""
Configuration Loader Utility
Loads and manages application configuration from YAML files.
"""

import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path


class ConfigLoader:
    """
    Singleton configuration loader that reads and manages application settings.

    Attributes:
        config (Dict[str, Any]): Loaded configuration dictionary
        config_path (Path): Path to the configuration file
    """

    _instance: Optional['ConfigLoader'] = None
    _config: Dict[str, Any] = {}

    def __new__(cls, config_path: Optional[str] = None):
        """Ensure only one instance of ConfigLoader exists."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.

        Args:
            config_path: Path to the configuration file. If None, uses default path.
        """
        if self._initialized:
            return

        if config_path is None:
            # Default to config/config.yaml in project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"

        self.config_path = Path(config_path)
        self._load_config()
        self._initialized = True

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f)

            # Create necessary directories based on config
            self._create_directories()

        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")

    def _create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        if 'paths' in self._config:
            project_root = Path(__file__).parent.parent.parent
            for key, path in self._config['paths'].items():
                full_path = project_root / path
                full_path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key using dot notation.

        Args:
            key: Configuration key (e.g., 'cameras.default_fps')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Examples:
            >>> config = ConfigLoader()
            >>> fps = config.get('cameras.default_fps', 30)
            >>> email = config.get('alerts.email.sender_email')
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value by key using dot notation.

        Args:
            key: Configuration key (e.g., 'cameras.default_fps')
            value: Value to set

        Examples:
            >>> config = ConfigLoader()
            >>> config.set('cameras.default_fps', 25)
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self, path: Optional[str] = None) -> None:
        """
        Save current configuration to file.

        Args:
            path: Path to save configuration. If None, uses original path.
        """
        save_path = Path(path) if path else self.config_path

        try:
            with open(save_path, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

    def get_all(self) -> Dict[str, Any]:
        """
        Get entire configuration dictionary.

        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.

        Args:
            section: Section name (e.g., 'cameras', 'alerts')

        Returns:
            Configuration section dictionary or empty dict if not found
        """
        return self._config.get(section, {}).copy()

    @property
    def config(self) -> Dict[str, Any]:
        """Get configuration dictionary."""
        return self._config

    def __repr__(self) -> str:
        return f"ConfigLoader(config_path='{self.config_path}')"

    def __str__(self) -> str:
        return f"Configuration loaded from: {self.config_path}"


# Convenience functions for global access
_global_config: Optional[ConfigLoader] = None


def get_config(config_path: Optional[str] = None) -> ConfigLoader:
    """
    Get global configuration instance.

    Args:
        config_path: Path to configuration file (only used on first call)

    Returns:
        Global ConfigLoader instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigLoader(config_path)
    return _global_config


def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get configuration value using global config instance.

    Args:
        key: Configuration key with dot notation
        default: Default value if key not found

    Returns:
        Configuration value
    """
    config = get_config()
    return config.get(key, default)


if __name__ == "__main__":
    # Test configuration loader
    config = ConfigLoader()
    print(config)
    print(f"App name: {config.get('app.name')}")
    print(f"Default FPS: {config.get('cameras.default_fps')}")
    print(f"Detection model: {config.get('detection.model')}")
    print(f"Alert enabled: {config.get('alerts.enabled')}")
