"""Configuration loader: merges settings.toml + environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[no-reattr]

# Project root = two levels up from this file (src/ai_price_monitor/config.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SETTINGS = _PROJECT_ROOT / "config" / "settings.toml"


def _load_toml(path: Path) -> dict:
    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def get_settings(settings_path: Path | None = None) -> dict:
    """Return merged configuration dict.

    Priority (high → low):
      1. Environment variables (AI_PRICE_MONITOR__SECTION__KEY)
      2. settings.toml from *settings_path* or default location
    """
    cfg = _load_toml(settings_path or _DEFAULT_SETTINGS)

    # Allow env-var overrides: AI_PRICE_MONITOR__GENERAL__USD_TO_CNY=7.3
    prefix = "AI_PRICE_MONITOR__"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split("__")
        node = cfg
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        # Best-effort type coercion
        try:
            node[parts[-1]] = int(value)
        except ValueError:
            try:
                node[parts[-1]] = float(value)
            except ValueError:
                node[parts[-1]] = value

    return cfg


# Module-level singleton (lazy)
_settings: dict | None = None


def settings() -> dict:
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def get(section: str, key: str, default=None):
    return settings().get(section, {}).get(key, default)
