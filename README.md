# TrackLyrics-ytdl

Local-first desktop app: download **audio** (mp3/wav) from YouTube with **yt-dlp**, keep a **SQLite** library, fetch **lyrics** from **letras.mus.br** (via DuckDuckGo HTML search, Playwright), and play audio with **PySide6** (`QMediaPlayer` + `QAudioOutput`). UI preferences live in **`app_settings.json`**.

## Documentation

| Document | Contents |
|----------|----------|
| [docs/architecture.md](docs/architecture.md) | System overview, dependencies, module map, cross-cutting rules |
| [docs/interface.md](docs/interface.md) | UI layout, widgets, theme, threading, dialogs |
| [docs/storage.md](docs/storage.md) | Paths, `library.db` schema, validation |
| [docs/player.md](docs/player.md) | Playback stack and behavior |
| [docs/scrapping.md](docs/scrapping.md) | Lyrics scraping flow (query, selectors, scoring) |

## Run

From the repository root, with Python 3.10+ and dependencies installed:

```bash
cd src && python main.py
```

Or set `PYTHONPATH` to `src` and run `python main.py` from `src/`. Install packages from `requirements.txt`; **FFmpeg** must be available for conversion where used.

## License

See [LICENSE](LICENSE).
