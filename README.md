# tg-grabber

Скрапит публичные Telegram-каналы и сохраняет полный архив постов + все
прикреплённые фото локально. **Без авторизации** — использует серверный
веб-превью `https://t.me/s/<channel>`, который Telegram отдаёт без логина.

Каждый пост и каждое фото сохраняются вместе с источником (каналом и
постоянной ссылкой на пост), чтобы любую перепубликацию можно было
по-честному атрибутировать.

---

## Что умеет

1. **`tg-grabber scrape`** — проходит весь архив канала от новейшего к старому
   (через пагинацию `?before=<id>`), складывает каждый пост в JSON: текст,
   дата, ссылки в тексте, URL'ы прикреплённых фото и video-thumbnails,
   просмотры, кто переслал.
2. **`tg-grabber media`** — берёт уже скачанные архивы и качает все
   фото-вложения локально. Пишет рядом `manifest.json`, где каждому файлу
   соответствует `channel`, `post_id`, ссылка на пост и оригинальный URL.
   Идемпотентно — можно прервать и продолжить.

## Что НЕ умеет

Веб-превью `t.me/s/` отдаёт только **текст + фото-превью**. Документы (PDF,
EPUB, книги), видео-файлы и аудио в HTML отсутствуют — для них нужен
Telegram MTProto API (Telethon/Pyrogram) с авторизацией пользователя.
Этот проект сознательно остаётся без авторизации.

---

## Установка

```bash
git clone <repo>
cd tg-grabber
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Или просто:

```bash
pip install -r requirements.txt
```

Зависимости: `requests`, `beautifulsoup4`, `PyYAML`. Python ≥ 3.9.

---

## Настройка каналов

Список каналов и параметры скрапа берутся из `channels.yaml`. Скопируйте
шаблон и впишите свои каналы:

```bash
cp channels.example.yaml channels.yaml
```

```yaml
# channels.yaml
channels:
  - example_channel        # имя без @, как в t.me/s/<name>
  - another_channel
delay: 1.0                 # сек между страницами — не опускай ниже 1
max_pages: 1000            # потолок пагинации (~20k постов)
```

`channels.yaml` в `.gitignore` — ваш список каналов не попадёт в репозиторий.
Путь к конфигу можно переопределить переменной `TG_CONFIG`.

---

## Использование

```bash
# Скрапим все каналы из channels.yaml
tg-grabber scrape

# Или явно указываем каналы (имя без @) — это переопределяет конфиг
tg-grabber scrape CHANNEL_NAME another_channel

# Качаем фото из ВСЕХ архивов
tg-grabber media

# Или только из конкретных каналов
tg-grabber media channel_name
```

Или через модуль:

```bash
python -m tg_grabber scrape
python -m tg_grabber media
```

### Куда складывается результат

По умолчанию всё кладётся в `./out/`:

```
out/
├── archives/                         ← JSON-архивы постов
│   ├── telegram_channel_name.json
│   └── telegram_another_channel.json
└── media/
    ├── manifest.json                 ← атрибуция (channel/post_id → источник)
    ├── channel_name/
    │   ├── 11_0.jpg
    │   ├── 11_1.jpg
    │   └── ...
    └── another_channel/
        └── ...
```

`out/` целиком в `.gitignore` — данные и фото остаются локально и не попадают
в репозиторий.

Пути можно переопределить через env-переменные:

```bash
export TG_OUT_DIR=/path/to/store        # корень
export TG_ARCHIVES_DIR=/path/to/json    # архивы постов
export TG_MEDIA_DIR=/path/to/photos     # фото-бинарники
```

---

## Формат архива (`telegram_<channel>.json`)

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

## Формат manifest медиа (`media/manifest.json`)

Ключ — относительный путь файла, значение — полный источник:

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

Имена файлов: `<channel>/<post_id>_<n>.<ext>` — по имени видно, из какого
канала и поста.

---

## Программный API

```python
from pathlib import Path
from tg_grabber import scrape_channel, download_media

# Скрап одного канала в любую папку
scrape_channel("CHANNEL_NAME", out_dir=Path("./out/archives"))

# Скачать фото из архивов в указанную папку
download_media(
    archives_dir="./out/archives",
    media_dir="./out/media",
    channels=["channel_name"],  # None = все архивы
    workers=8,
)
```

---

## Правило атрибуции

Это **публичный архив**, и контент остаётся собственностью авторов канала.
Если вы используете извлечённые тексты или фото в своих проектах:

- Сохраняйте ссылку на оригинальный пост (поле `url` в архиве,
  `source_url` в manifest).
- В метаданных вашего датасета указывайте источник в формате
  `@CHANNEL #post_id` или прямой URL поста.

Скрапер работает только с **публичными** каналами, читает только то, что
любой пользователь может открыть в браузере, и идёт с вежливой задержкой
1 сек между запросами.

---

## Известные ограничения

- **Документы/видео/аудио недоступны** — это ограничение веб-превью Telegram,
  не скрапера. Для них нужен MTProto-клиент.
- В постах с альбомами все фото складываются последовательно
  (`<post_id>_0.jpg`, `_1.jpg`, …).
- Иногда CDN-ссылки на старые фото истекают — такие файлы попадают в
  `failed` (видно в выводе). Повторный запуск может помочь, если ссылка
  ещё валидна.
- Скрапер ограничен `max_pages` страниц (по умолчанию 1000, ~20k постов
  максимум). Поправьте `max_pages` в `channels.yaml`, если канал больше.

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
