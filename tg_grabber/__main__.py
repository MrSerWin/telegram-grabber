"""CLI entry: ``python -m tg_grabber <command> [args]``.

Commands:
  scrape [channel ...]   Scrape channels' post archives. No args = channels
                         listed in channels.yaml (see channels.example.yaml).
  media  [channel ...]   Download photo previews from already-scraped archives.
                         No args = all archives found.
  fetch  [channel ...]   Download REAL files (video/audio/documents/photos) via
                         the MTProto API (needs telegram_api in channels.yaml
                         and a one-time login). No args = channels from config.

Output directories are taken from the env vars (with sensible defaults):
  TG_OUT_DIR      = ./out
  TG_ARCHIVES_DIR = $TG_OUT_DIR/archives
  TG_MEDIA_DIR    = $TG_OUT_DIR/media
  TG_FILES_DIR    = $TG_OUT_DIR/files

The channel list and settings come from channels.yaml (override the path with
TG_CONFIG); explicit channel args on the command line take priority.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from .config import ConfigError, DEFAULT_DELAY, DEFAULT_MAX_PAGES, load_config
from .media import download_media
from .scraper import scrape_channel


def _dirs() -> tuple[Path, Path, Path]:
    out = Path(os.environ.get("TG_OUT_DIR", "./out")).expanduser().resolve()
    archives = Path(os.environ.get("TG_ARCHIVES_DIR", out / "archives")).expanduser().resolve()
    media = Path(os.environ.get("TG_MEDIA_DIR", out / "media")).expanduser().resolve()
    files = Path(os.environ.get("TG_FILES_DIR", out / "files")).expanduser().resolve()
    return archives, media, files


def _usage() -> None:
    print(__doc__ or "", file=sys.stderr)
    sys.exit(2)


def main(argv: list[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        _usage()
    cmd, rest = args[0], args[1:]
    archives_dir, media_dir, files_dir = _dirs()

    if cmd == "scrape":
        delay, max_pages = DEFAULT_DELAY, DEFAULT_MAX_PAGES
        if rest:
            channels = [ch.lstrip("@").strip() for ch in rest]
        else:
            try:
                cfg = load_config()
            except ConfigError as e:
                print(e, file=sys.stderr)
                sys.exit(2)
            channels = cfg["channels"]
            delay, max_pages = cfg["delay"], cfg["max_pages"]
            print(f"[tg] {len(channels)} channel(s) from config: {', '.join(channels)}\n")
        for ch in channels:
            scrape_channel(ch, archives_dir, delay=delay, max_pages=max_pages)
    elif cmd == "media":
        download_media(archives_dir, media_dir, channels=[c.lstrip("@") for c in rest] or None)
    elif cmd == "fetch":
        try:
            cfg = load_config()
        except ConfigError as e:
            print(e, file=sys.stderr)
            sys.exit(2)
        if not cfg["api_id"] or not cfg["api_hash"]:
            print(
                "fetch needs Telegram API credentials. Add a telegram_api section "
                "to channels.yaml:\n"
                "  telegram_api:\n"
                "    api_id: 123456        # from https://my.telegram.org\n"
                '    api_hash: "..."',
                file=sys.stderr,
            )
            sys.exit(2)
        channels = [ch.lstrip("@").strip() for ch in rest] or cfg["channels"]
        from .fetch import fetch_files  # lazy: keeps Telethon optional

        asyncio.run(
            fetch_files(
                channels,
                api_id=cfg["api_id"],
                api_hash=cfg["api_hash"],
                session=cfg["session"],
                out_dir=files_dir,
                types=cfg["fetch_types"],
                limit=cfg["fetch_limit"],
            )
        )
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        _usage()


if __name__ == "__main__":
    main()
