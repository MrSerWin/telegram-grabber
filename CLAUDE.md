# CLAUDE.md

Instructions for Claude Code (and other LLM agents) working in this repo.
The `AGENTS.md` symlink points at this same file.

## What this is

`tg-grabber` scrapes public Telegram channels. It has two modes:

- **Auth-free** (`scrape` + `media`) via the server-rendered web preview at
  `t.me/s/<channel>` — text, links, and photo previews only.
- **MTProto** (`fetch`) via the authenticated Telegram API (Telethon) — the
  real files: video, audio, documents (PDF/EPUB/TXT/…), full-res photos.
  Opt-in, needs a login.

Each post keeps a `channel` field and a permalink `url`, and downloaded files
get a manifest, so any reuse can be attributed honestly.

Full user-facing docs are in [README.md](README.md).

## Layout

```
tg-grabber/
├── tg_grabber/
│   ├── __init__.py      ← public API: scrape_channel, download_media
│   ├── __main__.py      ← CLI: scrape / media / fetch
│   ├── config.py        ← reads channels.yaml (channels, settings, API creds)
│   ├── scraper.py       ← parses t.me/s/, paginates ?before=  (auth-free)
│   ├── media.py         ← downloads photo previews + manifest.json (auth-free)
│   └── fetch.py         ← MTProto file downloader (Telethon, opt-in, auth)
├── channels.example.yaml ← config template (in git)
├── channels.yaml          ← real channels + api_id/api_hash (in .gitignore)
├── out/                   ← all output (entirely in .gitignore)
│   ├── archives/          ← post archives (JSON)
│   ├── media/             ← photo previews (from `media`)
│   │   ├── manifest.json  ← attribution
│   │   └── <channel>/     ← photos
│   └── files/             ← real files (from `fetch`)
│       ├── manifest.json  ← attribution + media_type, original_name
│       └── <channel>/     ← videos, audio, documents
├── docs/channels.md     ← how to configure channels and what's in an archive
├── pyproject.toml       ← pip install -e .  → `tg-grabber` command
└── requirements.txt
```

## Commands

```bash
# Install
pip install -e .                              # installs the `tg-grabber` CLI
# or
pip install -r requirements.txt               # without the CLI command

# Setup: copy the template and add your channels
cp channels.example.yaml channels.yaml

# Scrape every channel in channels.yaml
tg-grabber scrape
python -m tg_grabber scrape                    # equivalent

# Scrape a specific channel (no @) — overrides the config
tg-grabber scrape CHANNEL_NAME                 # → out/archives/telegram_channel_name.json

# Download photo previews from ALL archives (idempotent — interruptible)
tg-grabber media

# Only from specific channels
tg-grabber media channel_name

# Download REAL files via MTProto (needs the extra + telegram_api in config)
pip install -e ".[mtproto]"
tg-grabber fetch                  # all channels from config
tg-grabber fetch CHANNEL_NAME     # or a specific one
```

Override the config path with `TG_CONFIG`. Output paths come from
`TG_OUT_DIR` (root), `TG_ARCHIVES_DIR`, `TG_MEDIA_DIR`, `TG_FILES_DIR`.

## Data formats

**`out/archives/telegram_<channel>.json`** — an array of posts; each has
`id`, `channel`, `url`, `datetime`, `text`, `links`, `images` (URLs),
`views`, `forwarded_from`. See [README.md](README.md#archive-format-telegram_channeljson).

**`out/media/manifest.json`** — `{ "<channel>/<id>_<n>.jpg": { channel,
post_id, source_url, image_url, datetime } }`. This is the attribution
source-of-truth. Do not change its format — downstream projects rely on it.

**`out/files/manifest.json`** (from `fetch`) — `{ "<channel>/<name>": {
channel, post_id, source_url, datetime, media_type, mime, original_name,
size } }`. Same attribution role for real files.

## Web-preview limitations (not bugs)

- `t.me/s/` serves **text + photo previews only**. Documents (PDF/EPUB),
  video files, audio, and stickers are unavailable via `scrape`/`media`.
  This is by design — to get those, use `fetch` (MTProto + login), which is
  what `tg_grabber/fetch.py` implements. Don't try to make the web scraper
  fetch files; it can't.
- Pagination is capped at `max_pages` (default 1000, ~20k posts). If a channel
  is larger, raise `max_pages` in `channels.yaml`.
- Old CDN links to photos may expire — those land in `failed` and the script
  carries on. Re-running later is normal (the link may have come back).
- The scraper waits 1 second between pages — don't reduce this aggressively.

## Working rules (important)

### Etiquette
- **Public channels only.** Don't add workarounds for private channels — that
  is a separate task and a different legal zone.
- **Don't drop `delay` below 1 second.** The scraper hits someone else's
  server; being polite is the only social norm of this tool.
- **Use a real browser User-Agent.** Don't spoof bots to bypass limits.

### Repository privacy
- This is an open repository. **Don't commit specific channel names**, the
  real `channels.yaml`, the contents of `out/`, or any scraped data.
  `.gitignore` blocks this — don't bypass it. Keep doc examples on
  placeholders (`CHANNEL_NAME`, `example_channel`).
- **Never commit secrets:** `api_id`/`api_hash` live in `channels.yaml` and the
  `*.session` file is a live login. Both are git-ignored — keep them that way.

### Attribution (critical)
- When writing code that uses extracted content, **always** keep the link to
  the source post. The `url` field in the archive, `source_url` in the manifest.
- For links embedded into other datasets, use the `@CHANNEL #post_id` form.
- Don't change the `manifest.json` format — downstream attribution relies on it.

### What not to do
- Don't auto-merge extracted text into someone else's dataset — posts may be
  essays with the author's judgments, and regexes produce a lot of noise.
  Manual or semi-manual reconciliation only, with the source cited.
- Don't commit photo binaries or scraped archives to git, even "temporarily."

## Programmatic API

```python
from pathlib import Path
from tg_grabber import scrape_channel, download_media

# Scrape one channel
scrape_channel("CHANNEL_NAME", out_dir=Path("./out/archives"))

# Download photos from archives
download_media(
    archives_dir="./out/archives",
    media_dir="./out/media",
    channels=["channel_name"],  # None = all archives in the directory
    workers=8,
)
```

## Tasks that naturally belong in this repo

- Improve parsing (e.g. capture polls or reactions if they appear in the HTML).
- Re-fetch failed photos with another `media` run.
- Add export to other formats (CSV, Parquet).
- Extend the config (e.g. per-channel settings).
