# Configuring channels

The list of channels to scrape and the scrape settings live in `channels.yaml`
at the repo root. That file is git-ignored — your channel list never ends up in
the repo. Start from the template:

```bash
cp channels.example.yaml channels.yaml
```

## `channels.yaml` format

```yaml
channels:
  - example_channel        # name without @, as in the URL t.me/s/<name>
  - another_channel

delay: 1.0                 # seconds between pages (keep >= 1)
max_pages: 1000            # pagination cap (~20k posts)
```

- **`channels`** — required list. The channel name comes from its public link
  `https://t.me/<name>` (the same as `t.me/s/<name>` for the web preview),
  without the `@`.
- **`delay`** — pause between page requests. The scraper hits someone else's
  server; keep a polite delay of ≥ 1 second.
- **`max_pages`** — limit on the number of pagination pages. Raise it if a
  channel is larger than ~20k posts.

Override the config path with the `TG_CONFIG` env var:

```bash
TG_CONFIG=/path/to/my-channels.yaml tg-grabber scrape
```

Channels passed explicitly on the command line override the config:

```bash
tg-grabber scrape some_channel other_channel
```

## What ends up in an archive

For each channel, `out/archives/telegram_<channel>.json` is created — an array
of posts. Each post has: `id`, `channel`, `url` (permalink), `datetime`,
`text`, `links` (URLs from the text), `images` (URLs of photos and video
thumbnails), `views`, `forwarded_from`. The full format is in
[README.md](../README.md#archive-format-telegram_channeljson).

`tg-grabber media` then downloads the photos from the archives and writes
`out/media/manifest.json`, attributing each file to its channel and post.

## What is NOT downloaded (a known limitation)

The `t.me/s/` web preview only serves text + photo previews. **Documents**
(PDF, EPUB), **video files**, and **audio** are absent from the channel's HTML
— that's not a scraper bug but a limitation of Telegram's public interface. To
fetch those, you need the Telegram MTProto API (Telethon/Pyrogram) with a
logged-in user.

URLs of external resources mentioned in posts are saved in each post's `links`
field — you can fetch them separately with plain HTTP requests.
