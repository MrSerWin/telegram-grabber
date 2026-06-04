"""Scrape the public web preview of a Telegram channel.

Telegram exposes a server-rendered, auth-free preview at ``t.me/s/<channel>``
that paginates backwards via ``?before=<message_id>``. We walk the whole
archive, extracting per-post: id, datetime, text, links, image/video-thumb
URLs and view count.

Every post keeps its source channel and permalink so reused content can be
attributed back to its origin.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)

_BG_RE = re.compile(r"background-image:\s*url\('([^']+)'\)")


def _text_with_breaks(node) -> str:
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    return node.get_text().strip()


def _parse_page(html: str, channel: str) -> tuple[list[dict], Optional[int]]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[dict] = []
    ids_on_page: list[int] = []

    for wrap in soup.select(".tgme_widget_message_wrap"):
        msg = wrap.select_one(".tgme_widget_message")
        if not msg:
            continue
        data_post = str(msg.get("data-post", ""))  # e.g. "channel/2912"
        try:
            mid = int(data_post.split("/")[-1])
        except (ValueError, IndexError):
            continue
        ids_on_page.append(mid)

        text_node = msg.select_one(".tgme_widget_message_text")
        text = _text_with_breaks(text_node)

        time_node = msg.select_one("time[datetime]")
        dt = time_node["datetime"] if time_node and time_node.has_attr("datetime") else None

        views_node = msg.select_one(".tgme_widget_message_views")
        views = views_node.get_text().strip() if views_node else None

        images: list[str] = []
        for el in msg.select(
            ".tgme_widget_message_photo_wrap, "
            ".tgme_widget_message_video_thumb, "
            "i.tgme_widget_message_roundvideo_thumb"
        ):
            style = str(el.get("style", ""))
            m = _BG_RE.search(style)
            if m:
                images.append(m.group(1))

        links: list[str] = []
        if text_node:
            for a in text_node.select("a[href]"):
                href = str(a["href"])
                if href and not href.startswith("#"):
                    links.append(href)

        fwd_node = msg.select_one(".tgme_widget_message_forwarded_from_name")
        forwarded_from = fwd_node.get_text().strip() if fwd_node else None

        posts.append({
            "id": mid,
            "channel": channel,
            "url": f"https://t.me/{channel}/{mid}",
            "datetime": dt,
            "text": text,
            "links": links,
            "images": images,
            "views": views,
            "forwarded_from": forwarded_from,
        })

    next_before = min(ids_on_page) if ids_on_page else None
    return posts, next_before


def scrape(channel: str, delay: float = 1.0, max_pages: int = 1000) -> list[dict]:
    """Walk a channel's public preview from newest to oldest and return all posts."""
    base = f"https://t.me/s/{channel}"
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    by_id: dict[int, dict] = {}
    before: Optional[int] = None
    pages = 0

    while pages < max_pages:
        url = base if before is None else f"{base}?before={before}"
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        posts, next_before = _parse_page(resp.text, channel)
        pages += 1

        new = 0
        for p in posts:
            if p["id"] not in by_id:
                by_id[p["id"]] = p
                new += 1

        print(
            f"[tg:{channel}] page {pages}: before={before} → "
            f"{len(posts)} posts ({new} new), total={len(by_id)}, "
            f"next_before={next_before}"
        )

        if next_before is None or (before is not None and next_before >= before) or new == 0:
            break
        before = next_before
        time.sleep(delay)

    return [by_id[k] for k in sorted(by_id)]


def scrape_channel(
    channel: str,
    out_dir: Path | str,
    delay: float = 1.0,
    max_pages: int = 1000,
) -> Path:
    """Scrape one channel and write ``<out_dir>/telegram_<channel>.json``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    posts = scrape(channel, delay=delay, max_pages=max_pages)
    out = out_dir / f"telegram_{channel.lower()}.json"
    payload = {
        "source": f"Telegram @{channel}",
        "source_url": f"https://t.me/{channel}",
        "scraped_via": "public web preview (t.me/s/)",
        "count": len(posts),
        "posts": posts,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with_text = sum(1 for p in posts if p["text"])
    with_img = sum(1 for p in posts if p["images"])
    print(
        f"[tg:{channel}] saved {len(posts)} posts → {out} "
        f"(text: {with_text}, images: {with_img})\n"
    )
    return out
