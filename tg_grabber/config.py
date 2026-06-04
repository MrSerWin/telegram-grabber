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
DEFAULT_SESSION = "tg_grabber"
ALL_FETCH_TYPES = ["video", "audio", "document", "photo"]


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

    # Optional MTProto section (only needed for the `fetch` command).
    api = data.get("telegram_api") or {}
    if not isinstance(api, dict):
        raise ConfigError(f"{fp}: 'telegram_api' must be a mapping")
    api_id = api.get("api_id")
    api_hash = api.get("api_hash")
    session = api.get("session") or DEFAULT_SESSION

    # Optional fetch settings.
    fetch = data.get("fetch") or {}
    if not isinstance(fetch, dict):
        raise ConfigError(f"{fp}: 'fetch' must be a mapping")
    fetch_types = fetch.get("types") or ALL_FETCH_TYPES
    if not isinstance(fetch_types, list) or not all(isinstance(t, str) for t in fetch_types):
        raise ConfigError(f"{fp}: 'fetch.types' must be a list of type names")
    unknown = sorted(set(fetch_types) - set(ALL_FETCH_TYPES))
    if unknown:
        raise ConfigError(
            f"{fp}: unknown fetch.types {unknown}; allowed: {ALL_FETCH_TYPES}"
        )
    fetch_limit = fetch.get("limit")
    if fetch_limit is not None:
        fetch_limit = int(fetch_limit)

    return {
        "channels": channels,
        "delay": float(delay),
        "max_pages": int(max_pages),
        "api_id": int(api_id) if api_id is not None else None,
        "api_hash": str(api_hash) if api_hash is not None else None,
        "session": str(session),
        "fetch_types": fetch_types,
        "fetch_limit": fetch_limit,
    }
