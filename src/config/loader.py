"""Configuration loader for SuperAgent."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from src.config.models import AgentConfig


def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    """Flatten a nested dictionary."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _nest_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert a flat dictionary with underscores to nested structure."""
    result: dict[str, Any] = {}
    
    # Map of flat keys to nested paths
    mappings = {
        "agent_model": ["model"],
        "agent_provider": ["provider"],
        "agent_max_iterations": ["max_iterations"],
        "agent_timeout": ["timeout"],
        "agent_temperature": ["temperature"],
        "agent_max_tokens": ["max_tokens"],
        "agent_reasoning_effort": ["reasoning", "effort"],
        "cache_enabled": ["cache", "enabled"],
        "cache_ttl": ["cache", "ttl"],
        "cache_min_chars": ["cache", "min_chars"],
        "retry_max_attempts": ["retry", "max_attempts"],
        "retry_base_delay": ["retry", "base_delay"],
        "retry_max_delay": ["retry", "max_delay"],
        "retry_retry_on_status": ["retry", "retry_on_status"],
        "tools_shell_enabled": ["tools", "shell_enabled"],
        "tools_shell_timeout": ["tools", "shell_timeout"],
        "tools_file_ops_enabled": ["tools", "file_ops_enabled"],
        "tools_max_file_size": ["tools", "max_file_size"],
        "tools_grep_enabled": ["tools", "grep_enabled"],
        "tools_max_grep_results": ["tools", "max_grep_results"],
        "output_mode": ["output", "mode"],
        "output_streaming": ["output", "streaming"],
        "output_colors": ["output", "colors"],
        "paths_cwd": ["paths", "cwd"],
        "paths_readable_roots": ["paths", "readable_roots"],
        "paths_writable_roots": ["paths", "writable_roots"],
    }
    
    for flat_key, value in flat.items():
        if flat_key in mappings:
            path = mappings[flat_key]
            current = result
            for part in path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[path[-1]] = value
    
    return result


def load_config_from_file(path: Path) -> AgentConfig:
    """Load configuration from a TOML file.
    
    Args:
        path: Path to the TOML configuration file.
        
    Returns:
        AgentConfig instance with loaded configuration.
        
    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If the config file is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    with open(path, "rb") as f:
        raw_config = tomllib.load(f)
    
    # TOML structure: [agent], [cache], [retry], etc.
    # We need to transform it to match our Pydantic model structure
    flat = _flatten_dict(raw_config)
    nested = _nest_dict(flat)
    
    # Also handle direct keys from [agent] section
    if "agent" in raw_config:
        for key, value in raw_config["agent"].items():
            if key not in nested:
                nested[key] = value
            if key == "reasoning" and isinstance(value, dict):
                nested["reasoning"] = value
    
    # Handle other top-level sections directly
    for section in ["cache", "retry", "tools", "output", "paths"]:
        if section in raw_config and section not in nested:
            nested[section] = raw_config[section]
    
    return AgentConfig(**nested)


def load_config(
    config_path: Optional[Path] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> AgentConfig:
    """Load configuration with optional overrides.
    
    Args:
        config_path: Optional path to a TOML config file.
        overrides: Optional dictionary of configuration overrides.
        
    Returns:
        AgentConfig instance.
    """
    # Start with defaults
    config_dict: dict[str, Any] = {}
    
    # Load from file if provided
    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            raw_config = tomllib.load(f)
        
        # Transform TOML structure
        if "agent" in raw_config:
            for key, value in raw_config["agent"].items():
                config_dict[key] = value
        
        for section in ["cache", "retry", "tools", "output", "paths"]:
            if section in raw_config:
                config_dict[section] = raw_config[section]
    
    # Apply overrides
    if overrides:
        for key, value in overrides.items():
            if "." in key:
                # Handle nested keys like "cache.enabled"
                parts = key.split(".")
                current = config_dict
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                config_dict[key] = value
    
    return AgentConfig(**config_dict)


def find_config_file() -> Optional[Path]:
    """Find the configuration file in standard locations.
    
    Searches in order:
    1. ./config.toml
    2. ./superagent.toml
    3. ~/.config/superagent/config.toml
    4. ~/.superagent/config.toml
    
    Returns:
        Path to the config file if found, None otherwise.
    """
    search_paths = [
        Path.cwd() / "config.toml",
        Path.cwd() / "superagent.toml",
        Path.home() / ".config" / "superagent" / "config.toml",
        Path.home() / ".superagent" / "config.toml",
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None
