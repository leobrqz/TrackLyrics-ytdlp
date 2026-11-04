<div align="center">

# TrackLyrics

Download audio from YouTube, fetch lyrics from letras.mus.br, organize a local music library, and listen in a desktop app built with Tauri and React.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![Tauri](https://img.shields.io/badge/Tauri-2-24C8DB?style=flat&logo=tauri&logoColor=white)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-TypeScript-149ECA?style=flat&logo=react&logoColor=white)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.3-red?style=flat)](https://github.com/yt-dlp/yt-dlp)

</div>

Runs on your machine: no account or cloud library. The Windows app keeps its database, settings, lyrics, and audio under **Documents/TrackLyrics**. Tauri development reuses an existing library in the repository root when present; otherwise it uses the same Documents folder.


Please read the [disclaimer](#disclaimer) before using this software.

## Stack

| Layer | Tech |
|-------|------|
| Desktop shell | Tauri 2 + Rust |
| UI | React + TypeScript + Vite |
| Styling | Tailwind CSS + project-owned design tokens |
| Local backend | Python sidecar over JSON Lines |
| Download and audio conversion | yt-dlp + FFmpeg |
| Storage | SQLite + local files |
| Lyrics lookup | BeautifulSoup, RapidFuzz, curl_cffi |

## Features

### Download & queue

- Paste **YouTube video** or **playlist** URLs (one per line); playlists are expanded into separate queue jobs (large playlists mean many sequential downloads).
- **Sequential or parallel queue** with progress and status for each job.
- **Duplicate detection** by normalized artist/title (warning only; does not block saving).

**MP3 audio quality:** yt-dlp format `bestaudio/best`; FFmpeg extract-audio; **192 kbps**.

**WAV audio quality:** yt-dlp format `bestaudio/best`; FFmpeg extract-audio to WAV; **no** explicit sample rate, channels, or bit depth in app code (FFmpeg defaults for `.wav`).

### Library & playlists

- **Search** the track list; **favorites** per track.
- **Playlists**: create, rename, add/remove tracks, **All tracks** vs playlist view.
- **View Metadata**: source URL, letras lyrics URLs, on-disk paths, format and file details.
- **Delete** removes DB row and track folder on disk.

### Lyrics

- Discovers **letras.mus.br** URLs by probing the canonical `/<artist-slug>/<title-slug>/` path.
- **Original** and **PT-BR** tabs when both exist; lyrics stored as `.md` under each track’s `lyrics/` folder.

### Player

- **Audio-only** playback: play/pause, prev/next, seek, volume.
- Queue follows the **current library or playlist** view.

### Interface

- A searchable library, playlists, lyrics reader, download queue, and persistent audio player in one desktop app.
- **Dark / light** theme with saved preferences.




## Setup

Download the Windows installer from the [releases](https://github.com/leobrqz/TrackLyrics-ytdl/releases) page, or run the app locally during development.


### 1. Clone the project

```bash
git clone https://github.com/leobrqz/TrackLyrics-ytdl.git
cd TrackLyrics-ytdlp
```


### 2. Install dependencies

Install the Python backend dependencies and frontend packages:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-backend.txt
npm ci
```


### 3. Start the app

On Windows, with Node.js 22+, Python 3.11+, and the Rust stable toolchain installed:

```powershell
npm run tauri:dev
```

The dev command starts the React interface and a source-mode Python sidecar. To build the desktop installers:

```powershell
npm run tauri:build
```

The build packages a Python sidecar and produces Windows MSI and NSIS installers. The sidecar includes FFmpeg for downloads and conversion; `ffprobe` details remain best-effort when `ffprobe` is not installed separately.


## License

See [LICENSE](LICENSE) (GNU General Public License v3).


## Disclaimer

This software is shared for **learning and personal experimentation** (desktop UI, local media libraries, automation concepts). It is **not** a commercial product and **not** offered as a tool to bypass restrictions or policies of third-party services.

This project is **not affiliated with**, endorsed by, or sponsored by YouTube, letras.mus.br, or any other third-party site or service it may interact with.

Lyrics retrieval uses **HTTP requests** to letras.mus.br. Downloading media relies on **yt-dlp**. **You** are solely responsible for how you use this software, including compliance with applicable **terms of service**, **copyright**, and **local laws**. The authors and contributors **do not** encourage or condone violating anyone’s ToS, scraping where prohibited, or infringing rights.

The software is provided **as-is**, without warranty; **no liability** is accepted for damages, account actions, or legal consequences arising from use or misuse.
