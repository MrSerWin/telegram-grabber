# tg-grabber

Scrapes public Telegram channels and saves a full archive of posts plus all
attached photos locally. **No authentication** — it uses the server-rendered
web preview at `https://t.me/s/<channel>` that Telegram serves without login.

Every post and every photo is saved together with its source (channel and
permalink to the post), so any reuse can be attributed honestly.

---

## What it does

1. **`tg-grabber scrape`** — walks a channel's whole archive from newest to
   oldest (paginating via `?before=<id>`) and stores each post as JSON: text,
   date, in-text links, URLs of attached photos and video thumbnails, view
   count, and who forwarded it.
2. **`tg-grabber media`** — takes the already-scraped archives and downloads
   every photo attachment locally. It writes a `manifest.json` next to them
   mapping each file to its `channel`, `post_id`, post permalink, and original
   URL. Idempotent — you can interrupt and resume.
3. **`tg-grabber fetch`** — downloads the **real files** (videos, audio/music,
   documents — PDF/EPUB/TXT/…, full-res photos) via the authenticated Telegram
   MTProto API. This is the only way to get anything beyond text + photo
   previews. Requires a one-time login. See
   [Downloading real files](#downloading-real-files-fetch).

## Two modes: auth-free vs MTProto

| | `scrape` / `media` | `fetch` |
|---|---|---|
| Source | `t.me/s/` web preview | MTProto API |
| Auth | none | one-time login (api_id/api_hash) |
| Gets | text, links, photo previews | videos, audio, documents, full-res photos |
| Dependency | base | `tg-grabber[mtproto]` (Telethon) |

The auth-free `t.me/s/` web preview only serves **text + photo previews** —
videos, audio, and documents (PDF, EPUB, books) are absent from that HTML. To
download those you must use `fetch`, which talks to the Telegram MTProto API
with a logged-in user. The auth-free path stays the default; `fetch` is opt-in.

---

## Installation

```bash
git clone <repo>
cd tg-grabber
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Or just:

```bash
pip install -r requirements.txt
```

Dependencies: `requests`, `beautifulsoup4`, `PyYAML`. Python ≥ 3.9.

For the `fetch` command (real files via MTProto), also install the extra:

```bash
pip install -e ".[mtproto]"        # adds Telethon
```

---

## Configuring channels

The channel list and scrape settings come from `channels.yaml`. Copy the
template and add your channels:

```bash
cp channels.example.yaml channels.yaml
```

```yaml
# channels.yaml
channels:
  - example_channel        # name without @, as in t.me/s/<name>
  - another_channel
delay: 1.0                 # seconds between pages — keep >= 1
max_pages: 1000            # pagination cap (~20k posts)
```

`channels.yaml` is git-ignored — your channel list never ends up in the repo.
Override the config path with the `TG_CONFIG` env var.

---

## Usage

```bash
# Scrape every channel listed in channels.yaml
tg-grabber scrape

# Or pass channels explicitly (name without @) — this overrides the config
tg-grabber scrape CHANNEL_NAME another_channel

# Download photos from ALL archives
tg-grabber media

# Or only from specific channels
tg-grabber media channel_name
```

Or via the module:

```bash
python -m tg_grabber scrape
python -m tg_grabber media
```

### Where output goes

By default everything lands in `./out/`:

```
out/
├── archives/                         ← post archives (JSON)
│   ├── telegram_channel_name.json
│   └── telegram_another_channel.json
├── media/                            ← photo previews (from `media`)
│   ├── manifest.json                 ← attribution (channel/post_id → source)
│   ├── channel_name/
│   │   ├── 11_0.jpg
│   │   └── ...
│   └── another_channel/
└── files/                            ← real files (from `fetch`)
    ├── manifest.json                 ← attribution + media_type, original_name
    └── channel_name/
        ├── 70_book-title.pdf
        ├── 81_0.mp4
        └── ...
```

The whole `out/` directory is git-ignored — data and photos stay local and
never get committed.

Paths can be overridden via env vars:

```bash
export TG_OUT_DIR=/path/to/store        # root
export TG_ARCHIVES_DIR=/path/to/json    # post archives
export TG_MEDIA_DIR=/path/to/photos     # photo previews
export TG_FILES_DIR=/path/to/files      # real files (fetch)
```

---

## Downloading real files (`fetch`)

`fetch` uses the authenticated Telegram MTProto API to download the actual
files — videos, audio/music, documents (PDF/EPUB/TXT/…) and full-resolution
photos — which the auth-free web preview cannot reach.

**1. Install the extra:**

```bash
pip install -e ".[mtproto]"
```

**2. Get API credentials** at <https://my.telegram.org> → *API development
tools* → note your `api_id` and `api_hash`, and add them to `channels.yaml`:

```yaml
telegram_api:
  api_id: 123456
  api_hash: "your_api_hash"
  session: tg_grabber        # session file name (git-ignored)

fetch:
  types: [video, audio, document, photo]   # which kinds to download
  limit: null                # max messages per channel (null = all)
```

**3. Run it** (the first run logs you in interactively — phone number + the
code Telegram sends you, plus 2FA password if enabled):

```bash
tg-grabber fetch                  # all channels from channels.yaml
tg-grabber fetch CHANNEL_NAME     # or a specific one
```

Files land in `out/files/<channel>/`, with `out/files/manifest.json` recording
each file's `channel`, `post_id`, `source_url`, `media_type`, `mime` and
`original_name`. The run is idempotent — existing files are skipped.

> **Security:** `channels.yaml` holds your `api_id`/`api_hash` and `*.session`
> is your login — both are git-ignored. Never commit them.

> **Note:** `fetch` accesses Telegram as your logged-in account. Use it only on
> channels you may lawfully access, and mind each channel's content rights.

---

## Archive format (`telegram_<channel>.json`)

```jsonc
{
  "source": "Telegram @CHANNEL_NAME",
  "source_url": "https://t.me/CHANNEL_NAME",
  "scraped_via": "public web preview (t.me/s/)",
  "count": 1294,
  "posts": [
    {
      "id": 11,
      "channel": "CHANNEL_NAME",
      "url": "https://t.me/CHANNEL_NAME/11",
      "datetime": "2020-08-28T14:23:54+00:00",
      "text": "...",
      "links": ["https://example.com/..."],
      "images": ["https://cdn4.telesco.pe/file/..."],
      "views": "1.2K",
      "forwarded_from": null
    }
  ]
}
```

## Media manifest format (`media/manifest.json`)

The key is the file's relative path, the value is its full source:

```jsonc
{
  "channel_name/70_0.jpg": {
    "channel": "channel_name",
    "post_id": 70,
    "source_url": "https://t.me/CHANNEL_NAME/70",
    "image_url": "https://cdn4.telesco.pe/file/...",
    "datetime": "2020-10-16T18:35:17+00:00"
  }
}
```

File names: `<channel>/<post_id>_<n>.<ext>` — the name alone tells you which
channel and post a photo came from.

---

## Programmatic API

```python
from pathlib import Path
from tg_grabber import scrape_channel, download_media

# Scrape one channel into any folder
scrape_channel("CHANNEL_NAME", out_dir=Path("./out/archives"))

# Download photo previews from archives into a given folder
download_media(
    archives_dir="./out/archives",
    media_dir="./out/media",
    channels=["channel_name"],  # None = all archives
    workers=8,
)

# Download real files via MTProto (needs `tg-grabber[mtproto]` + credentials)
import asyncio
from tg_grabber.fetch import fetch_files

asyncio.run(fetch_files(
    ["channel_name"],
    api_id=123456,
    api_hash="your_api_hash",
    session="tg_grabber",
    out_dir="./out/files",
    types=["video", "audio", "document", "photo"],
    limit=None,
))
```

---

## Attribution rule

This is a **public archive**, and the content remains the property of the
channel authors. If you use extracted text or photos in your own projects:

- Keep the link to the original post (the `url` field in the archive,
  `source_url` in the manifest).
- In your dataset's metadata, cite the source as `@CHANNEL #post_id` or the
  direct post URL.

The scraper only works with **public** channels, reads only what any user can
open in a browser, and runs with a polite 1-second delay between requests.

---

## Known limitations

- **Documents/video/audio need `fetch`** — the auth-free `scrape`/`media` path
  only sees text + photo previews. Use [`fetch`](#downloading-real-files-fetch)
  (MTProto, with login) for the real files.
- In posts with albums, photos are stored sequentially
  (`<post_id>_0.jpg`, `_1.jpg`, …).
- Sometimes CDN links to old photos expire — those files land in `failed`
  (shown in the output). A later re-run may help if the link is still valid.
- The scraper is capped at `max_pages` pages (default 1000, ~20k posts max).
  Raise `max_pages` in `channels.yaml` if a channel is larger.

---

## License

MIT — see [LICENSE](LICENSE).
