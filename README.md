<div align="center">

# TrackLyrics

Download **songs** from YouTube, fetch **lyrics** from **letras.mus.br** and play everything with a **PySide6** UI.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/PySide-6-green?style=flat&logo=qt)](https://doc.qt.io/qtforpython-6/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.3-red?style=flat)](https://github.com/yt-dlp/yt-dlp)

</div>

Runs entirely on your machine: no accounts, no cloud library. Theme and simple preferences persist in **`app_settings.json`** next to **`library.db`** and your **`tracks/`** folder.


Please read the [disclaimer](#disclaimer) before using this software.

## Stack

| Layer | Tech |
|-------|------|
| UI | PySide6 |
| Download | yt-dlp (+ FFmpeg for extract-audio) |
| Storage | SQLite + filesystem |
| Lyrics | BeautifulSoup, RapidFuzz, curl_cffi |

## Features

### Download & queue

- Paste **YouTube video** or **playlist** URLs (one per line); playlists are expanded into separate queue jobs (large playlists mean many sequential downloads).
- **Sequential queue** with progress and status in the bottom strip.
- **Duplicate detection** by normalized artist/title (warning only; does not block saving).

**MP3 audio quality:** yt-dlp format `bestaudio/best`; FFmpeg extract-audio; **192 kbps**.

**WAV audio quality:** yt-dlp format `bestaudio/best`; FFmpeg extract-audio to WAV; **no** explicit sample rate, channels, or bit depth in app code (FFmpeg defaults for `.wav`).

### Library & playlists

- **Search** the track list; **favorites** (star) per track.
- **Playlists**: create, rename, add/remove tracks, **All tracks** vs playlist view.
- **View Metadata…** (right-click a track): source URL, letras lyrics URLs, on-disk paths, format and file details.
- **Delete** removes DB row and track folder on disk.

### Lyrics

- Discovers **letras.mus.br** URLs by probing the canonical `/<artist-slug>/<title-slug>/` path (HTTP only, no browser automation).
- **Original** and **PT-BR** tabs when both exist; lyrics stored as `.md` under each track’s `lyrics/` folder.

### Player

- **Audio-only** playback: play/pause, prev/next, seek, volume.
- Queue follows the **current library or playlist** view.

### Interface

- **Dark / light** theme from the toolbar.
- **Window icon** from `assets/icon.ico` when that file is present at the app root.




## Setup

You can either run the app yourself with Python or download the .exe file from the [releases](https://github.com/leobrqz/TrackLyrics-ytdl/releases) page.


### 1. Clone the project

```bash
git clone https://github.com/leobrqz/TrackLyrics-ytdl.git
cd TrackLyrics-ytdlp
```


### 2. Install dependencies

- Set up Python environment

```bash
pip install -r requirements.txt
```


### 3. Start the app

From the repository root:

```bash
cd src && python main.py
```


## License

See [LICENSE](LICENSE) (GNU General Public License v3).


## Disclaimer

This software is shared for **learning and personal experimentation** (desktop UI, local media libraries, automation concepts). It is **not** a commercial product and **not** offered as a tool to bypass restrictions or policies of third-party services.

This project is **not affiliated with**, endorsed by, or sponsored by YouTube, letras.mus.br, or any other third-party site or service it may interact with.

Lyrics retrieval uses **HTTP requests** to letras.mus.br. Downloading media relies on **yt-dlp**. **You** are solely responsible for how you use this software, including compliance with applicable **terms of service**, **copyright**, and **local laws**. The authors and contributors **do not** encourage or condone violating anyone’s ToS, scraping where prohibited, or infringing rights.

The software is provided **as-is**, without warranty; **no liability** is accepted for damages, account actions, or legal consequences arising from use or misuse.
