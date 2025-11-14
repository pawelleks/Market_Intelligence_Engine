"""
Lightweight config loader.
Functions load YAML configs lazily to avoid requiring PyYAML at import time.
"""
from pathlib import Path
from typing import Any, Dict


def load_yaml(path: str) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict.

    PyYAML is imported inside the function to keep module import lightweight.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        import yaml
    except Exception as e:
        raise RuntimeError("PyYAML is required to load YAML files. Install pyyaml.") from e
    with p.open("r") as fh:
        return yaml.safe_load(fh) or {}


def load_named_config(name: str, config_dir: str = "config") -> Dict[str, Any]:
    """Load a config file from the config directory by name (without extension).
    Example: load_named_config('tickers') reads 'config/tickers.yml'
    """
    cfg_path = Path(config_dir) / f"{name}.yml"
    return load_yaml(str(cfg_path))

