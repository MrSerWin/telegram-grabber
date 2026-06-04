"""Download images referenced in scraped Telegram archives, with attribution.

Reads ``<archives_dir>/telegram_*.json`` and downloads the photo/video-thumb
URLs to ``<media_dir>/<channel>/<post_id>_<n>.<ext>``. A sidecar
``<media_dir>/manifest.json`` maps each saved file back to its source —
channel, post id, post permalink, original image URL and date — so reused
photos can always be credited honestly.

Idempotent: already-downloaded files are skipped, so the run can be
interrupted and resumed. Modest concurrency to stay polite to the CDN.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests

from .scraper import UA

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _ext(url: str) -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    return ext if ext in _IMG_EXTS else ".jpg"


def _jobs_from_archives(archives_dir: Path, channels: Iterable[str] | None) -> list[dict]:
    wanted = {c.lower() for c in channels} if channels else None
    jobs: list[dict] = []
    for fp in sorted(archives_dir.glob("telegram_*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        channel = fp.stem.replace("telegram_", "")
        if wanted is not None and channel not in wanted:
            continue
        for p in data["posts"]:
            for n, img_url in enumerate(p.get("images") or []):
                rel = f"{channel}/{p['id']}_{n}{_ext(img_url)}"
                jobs.append({
                    "rel": rel,
                    "image_url": img_url,
                    "channel": channel,
                    "post_id": p["id"],
                    "post_url": p["url"],
                    "datetime": p.get("datetime"),
                })
    return jobs


def _download(session: requests.Session, media_dir: Path, job: dict) -> tuple[dict, bool, str]:
    dest = media_dir / job["rel"]
    if dest.exists() and dest.stat().st_size > 0:
        return job, True, "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = session.get(job["image_url"], timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return job, True, "ok"
    except Exception as e:  # noqa: BLE001
        return job, False, str(e)[:80]


def download_media(
    archives_dir: Path | str,
    media_dir: Path | str,
    channels: Iterable[str] | None = None,
    workers: int = 8,
) -> dict:
    """Download every image referenced in scraped archives.

    Returns counts ``{ok, skip, fail, manifest_entries}``.
    """
    archives_dir = Path(archives_dir)
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = media_dir / "manifest.json"

    jobs = _jobs_from_archives(archives_dir, channels)
    if not jobs:
        print("[media] nothing to download")
        return {"ok": 0, "skip": 0, "fail": 0, "manifest_entries": 0}
    print(f"[media] {len(jobs)} image(s) queued")

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    manifest: dict[str, dict] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    ok = skip = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_download, session, media_dir, j) for j in jobs]
        for i, fut in enumerate(as_completed(futures), 1):
            job, success, status = fut.result()
            if success:
                manifest[job["rel"]] = {
                    "channel": job["channel"],
                    "post_id": job["post_id"],
                    "source_url": job["post_url"],
                    "image_url": job["image_url"],
                    "datetime": job["datetime"],
                }
                if status == "skip":
                    skip += 1
                else:
                    ok += 1
            else:
                fail += 1
            if i % 250 == 0:
                print(f"[media] {i}/{len(jobs)} (ok={ok} skip={skip} fail={fail})")
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[media] done: downloaded {ok}, skipped {skip}, failed {fail}")
    print(f"[media] files → {media_dir}")
    print(f"[media] attribution manifest → {manifest_path} ({len(manifest)} entries)")
    return {"ok": ok, "skip": skip, "fail": fail, "manifest_entries": len(manifest)}
