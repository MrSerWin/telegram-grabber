"""Load the list of channels to scrape (and scrape settings) from YAML.

By default reads ``channels.yaml`` from the current directory; override with
the ``TG_CONFIG`` env var. The file is git-ignored — copy
``channels.example.yaml`` to ``channels.yaml`` and put your channels there.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_CONFIG = "channels.yaml"
DEFAULT_DELAY = 1.0
DEFAULT_MAX_PAGES = 1000


class ConfigError(Exception):
    """Raised when the channel config is missing or malformed."""


def config_path(path: str | Path | None = None) -> Path:
    """Resolve the config path: explicit arg → ``TG_CONFIG`` env → default."""
    chosen = path or os.environ.get("TG_CONFIG") or DEFAULT_CONFIG
    return Path(chosen).expanduser()


def load_config(path: str | Path | None = None) -> dict:
    """Load scrape config from YAML.

    Returns ``{channels: list[str], delay: float, max_pages: int}``.
    Raises :class:`ConfigError` if the file is missing or has no channels.
    """
    fp = config_path(path)
    if not fp.exists():
        raise ConfigError(
            f"config not found: {fp}\n"
            "Copy channels.example.yaml to channels.yaml and list your channels, "
            "or pass channel names on the command line."
        )

    data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{fp}: expected a YAML mapping at the top level")

    channels = data.get("channels") or []
    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        raise ConfigError(f"{fp}: 'channels' must be a list of channel names")
    channels = [c.lstrip("@").strip() for c in channels if c and c.strip()]
    if not channels:
        raise ConfigError(f"{fp}: no channels listed under 'channels'")

    delay = data.get("delay", DEFAULT_DELAY)
    max_pages = data.get("max_pages", DEFAULT_MAX_PAGES)

    return {
        "channels": channels,
        "delay": float(delay),
        "max_pages": int(max_pages),
    }
