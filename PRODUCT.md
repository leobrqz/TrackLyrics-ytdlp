# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Approved migration direction: Tauri 2 desktop shell with React, TypeScript, and Vite; Tailwind backed by project-owned CSS variables and components; Python retained as a packaged sidecar during the first migration. This replaces the current PySide6 interface incrementally.

## Users

The current workflows are for an individual managing and listening to a local music library. The repository does not define a more specific audience or use case.

## Product Purpose

TrackLyrics downloads audio from YouTube through yt-dlp, looks up lyrics on letras.mus.br, organizes tracks and playlists in a local library, and plays supported audio files.

## Positioning

The library, settings, lyrics, and playback are local. The current product has no account or cloud-library requirement.

## Operating Context

- The current desktop app targets Windows and is built with PySide6.
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
- The backend is Python today. The download worker and audio player still depend on Qt and need to be detached from PySide6 before they can run behind the new UI.
- The app currently relies on FFmpeg/ffprobe being available externally; packaging behavior must be made explicit before shipping a Tauri installer.

## Brand Commitments

- Keep the product name TrackLyrics and its existing icon asset (`assets/icon.ico`).
- The user asks for an exceptionally polished, fluid desktop interface with a clean quality bar comparable to Apple and Linear, without generic AI-generated styling or filler copy.

## Evidence on Hand

- Product behavior and supported formats: `README.md`.
- Existing workflows and interaction states: `src/ui/main_window.py`, `src/ui/widgets/`, and `src/ui/dialogs/`.
- SQLite schema and data paths: `src/core/database.py` and `src/utils/paths.py`.
- The repository currently contains an application icon, but no album-art catalog or other approved cover imagery. Do not fabricate artwork or product claims.

## Product Principles

- Keep the user's music library and preferences on their machine.
- Make downloading, organizing, reading lyrics, and listening work together as one product.
- Show truthful progress, availability, and errors for each item or action.
- Preserve existing library data and behavior through the migration.
- Give every primary workflow equal care and a clear place in the interface.
