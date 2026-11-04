# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Approved migration: Tauri 2 desktop shell with React, TypeScript, and Vite; Tailwind backed by project-owned CSS variables and components; Python retained as a packaged sidecar.

## Users

The current workflows are for an individual managing and listening to a local music library. The repository does not define a more specific audience or use case.

## Product Purpose

TrackLyrics downloads audio from YouTube through yt-dlp, looks up lyrics on letras.mus.br, organizes tracks and playlists in a local library, and plays supported audio files.

## Positioning

The library, settings, lyrics, and playback are local. The current product has no account or cloud-library requirement.

## Operating Context

- The desktop app targets Windows and runs its React frontend inside Tauri.
- The current release stores its database, settings, track folders, temporary files, and logs under `Documents/TrackLyrics`; development data is stored beside the repository.
- A track can be selected from the current library or playlist view and played in sequence.
- The interface currently uses English labels and supports dark and light themes.

## Capabilities and Constraints

- Add YouTube video or playlist URLs; playlist inputs expand into individual download jobs.
- Download MP3 or WAV audio through yt-dlp and FFmpeg. MP3 uses 192 kbps; WAV uses FFmpeg defaults.
- Track a download queue, per-job progress, failures, and duplicate warnings. A duplicate is a warning and does not block saving.
- Search tracks, mark favorites, create and manage playlists, inspect metadata, and delete a track and its local folder.
- Retrieve original and PT-BR lyrics when available; lyrics and media are stored in each track's local folder.
- Play MP3 and WAV files with previous, next, seek, and volume controls. Playback follows the current library or playlist view.
- Preserve existing SQLite schema, settings, and media folders during the frontend migration. Any data-directory change requires an explicit migration with backup and verification.
- All existing workflows—library, lyrics, player, and downloads—remain first-class in the migrated interface.
- UI feedback must describe real application state and offer useful next actions. Do not invent system or network status messages.
- The Python backend communicates with the Tauri shell through JSON Lines. Its download worker is independent of Qt; playback uses WebView audio for validated MP3/WAV files.
- FFmpeg is included in the packaged Python sidecar through `imageio-ffmpeg`; `ffprobe` remains optional for best-effort media details.

## Brand Commitments

- Keep the product name TrackLyrics and its existing icon asset (`assets/icon.ico`).
- The user asks for an exceptionally polished, fluid desktop interface with a clean quality bar comparable to Apple and Linear, without generic AI-generated styling or filler copy.

## Evidence on Hand

- Product behavior and supported formats: `README.md`.
- Current workflows and interaction states: `web/src/App.tsx` and `web/src/styles.css`.
- Sidecar commands/events, SQLite schema, and data paths: `src/sidecar/main.py`, `src/core/database.py`, and `src/utils/paths.py`.
- The repository currently contains an application icon, but no album-art catalog or other approved cover imagery. Do not fabricate artwork or product claims.

## Product Principles

- Keep the user's music library and preferences on their machine.
- Make downloading, organizing, reading lyrics, and listening work together as one product.
- Show truthful progress, availability, and errors for each item or action.
- Preserve existing library data and behavior through the migration.
- Give every primary workflow equal care and a clear place in the interface.
