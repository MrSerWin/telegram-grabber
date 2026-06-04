"""Download real media and files from Telegram channels via the MTProto API.

Unlike the auth-free ``t.me/s/`` web preview (see :mod:`tg_grabber.scraper`),
which only exposes text and photo previews, the MTProto API serves the actual
files: videos, audio/music, and documents (PDF, EPUB, TXT, ...). This requires
a logged-in user session — ``api_id``/``api_hash`` from https://my.telegram.org
plus an interactive first-time login.

Files are saved to ``<out_dir>/<channel>/`` and a sidecar
``<out_dir>/manifest.json`` maps each file back to its source — channel, post
id, permalink, media type and original name — so reused files can always be
credited honestly.

Idempotent: already-downloaded files are skipped, so a run can be interrupted
and resumed.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Iterable, Optional

ALL_TYPES = ["video", "audio", "document", "photo"]

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _require_telethon():
    """Import Telethon lazily with a helpful message if it's missing."""
    try:
        from telethon import TelegramClient  # noqa: F401
        from telethon import errors  # noqa: F401
        import telethon  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "The `fetch` command needs Telethon (MTProto). Install it with:\n"
            '    pip install "tg-grabber[mtproto]"'
        ) from e
    return telethon


def _safe(name: str) -> str:
    """Sanitize an original filename into a path-safe component."""
    name = _SAFE_NAME_RE.sub("_", name).strip("._")
    return name or "file"


def _classify(message) -> Optional[str]:
    """Map a Telethon message's media to one of ALL_TYPES, or None."""
    if message.video or message.video_note or message.gif:
        return "video"
    if message.audio or message.voice:
        return "audio"
    if message.photo:
        return "photo"
    if message.document:  # any other document: pdf/epub/txt/docx/...
        return "document"
    return None


def _dest_name(message, seq: int) -> str:
    """Build ``<post_id>_<name>`` / ``<post_id>_<seq>.<ext>``."""
    pid = message.id
    original = getattr(message.file, "name", None) if message.file else None
    if original:
        return f"{pid}_{_safe(original)}"
    ext = (getattr(message.file, "ext", None) if message.file else None) or ""
    return f"{pid}_{seq}{ext}"


async def fetch_files(
    channels: Iterable[str],
    *,
    api_id: int,
    api_hash: str,
    session: str = "tg_grabber",
    out_dir: Path | str = "./out/files",
    types: Iterable[str] | None = None,
    limit: Optional[int] = None,
) -> dict:
    """Download files from channels over MTProto. Returns ``{ok, skip, fail, manifest_entries}``.

    ``types`` filters which media kinds to download (default: all of
    :data:`ALL_TYPES`). ``limit`` caps messages scanned per channel
    (None = all). The first run logs in interactively and creates
    ``<session>.session``.
    """
    _require_telethon()
    from telethon import TelegramClient
    from telethon import errors

    wanted = set(types) if types else set(ALL_TYPES)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest: dict[str, dict] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    ok = skip = fail = 0

    def _save_manifest() -> None:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    client = TelegramClient(session, api_id, api_hash)
    await client.start()
    try:
        me = await client.get_me()
        print(f"[fetch] logged in as {getattr(me, 'username', None) or me.id}")
        for channel in channels:
            ch = channel.lstrip("@").strip()
            ch_dir = out_dir / ch.lower()
            print(f"[fetch:{ch}] scanning (types={sorted(wanted)}, limit={limit})")
            seen = 0
            async for message in client.iter_messages(ch, limit=limit):
                media_type = _classify(message)
                if media_type is None or media_type not in wanted:
                    continue
                seen += 1
                rel = f"{ch.lower()}/{_dest_name(message, seen)}"
                dest = out_dir / rel

                if dest.exists() and dest.stat().st_size > 0:
                    skip += 1
                    manifest[rel] = _entry(ch, message, media_type, dest)
                    continue

                ch_dir.mkdir(parents=True, exist_ok=True)
                try:
                    await client.download_media(message, file=str(dest))
                    if not (dest.exists() and dest.stat().st_size > 0):
                        fail += 1
                        continue
                    ok += 1
                    manifest[rel] = _entry(ch, message, media_type, dest)
                except errors.FloodWaitError as e:  # belt-and-suspenders; Telethon usually waits
                    print(f"[fetch:{ch}] flood wait {e.seconds}s, sleeping")
                    await asyncio.sleep(e.seconds + 1)
                    fail += 1
                    continue
                except Exception as e:  # noqa: BLE001
                    print(f"[fetch:{ch}] {rel}: {str(e)[:100]}")
                    fail += 1
                    continue

                if (ok + skip) % 50 == 0:
                    print(f"[fetch:{ch}] ok={ok} skip={skip} fail={fail}")
                    _save_manifest()
            print(f"[fetch:{ch}] done ({seen} matching message(s))")
    finally:
        await client.disconnect()

    _save_manifest()
    print(f"\n[fetch] done: downloaded {ok}, skipped {skip}, failed {fail}")
    print(f"[fetch] files → {out_dir}")
    print(f"[fetch] attribution manifest → {manifest_path} ({len(manifest)} entries)")
    return {"ok": ok, "skip": skip, "fail": fail, "manifest_entries": len(manifest)}


def _entry(channel: str, message, media_type: str, dest: Path) -> dict:
    dt = message.date.isoformat() if message.date else None
    f = message.file
    return {
        "channel": channel,
        "post_id": message.id,
        "source_url": f"https://t.me/{channel}/{message.id}",
        "datetime": dt,
        "media_type": media_type,
        "mime": getattr(f, "mime_type", None) if f else None,
        "original_name": getattr(f, "name", None) if f else None,
        "size": dest.stat().st_size if dest.exists() else None,
    }
