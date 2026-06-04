"""tg-grabber — scrape public Telegram channels' posts and media.

Reads ``https://t.me/s/<channel>`` (the auth-free preview), paginates backwards
via ``?before=<message_id>`` and saves every post (text, links, image URLs,
date, views) to a JSON archive. A companion downloader fetches the referenced
images locally and writes a manifest so reused photos can be credited honestly.
"""
from .scraper import scrape_channel, scrape
from .media import download_media

__all__ = ["scrape_channel", "scrape", "download_media"]
__version__ = "0.1.0"
