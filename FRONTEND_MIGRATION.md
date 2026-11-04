# TrackLyrics frontend migration

## Goal

Replace the PySide6 interface with a desktop application built on Tauri and a web frontend. The work covers the complete current product: library, playlists, lyrics, playback, download queue, and settings. It preserves the local library and established download behavior while giving the interface a precise, fluid, production-quality design.

## Decisions

- **Desktop shell:** Tauri 2.
- **Frontend:** React, TypeScript, and Vite.
- **Styling:** Tailwind for layout and composition; project-owned CSS variables and components define the visual system. Use accessible interaction primitives where useful, without inheriting a generic kit's appearance.
- **Backend for the first migration:** retain the existing Python core as a bundled sidecar. Separate its JSONL request/event protocol from logs. Keep the frontend behind typed Tauri commands and events.
- **Player:** move playback controls and queue state into the frontend and use WebView audio for local MP3/WAV playback, subject to validation in the packaged Windows build. Expose only validated files inside the existing track library.
- **Storage:** preserve the existing `Documents/TrackLyrics` data root for the initial Windows release. Keep the SQLite schema, settings, and track folders intact. Do not initialize an empty database at a new path when an existing library is available.
- **Build direction:** code-first, confirmed by the user.
- **Experience priority:** library, lyrics, player, and downloads are all first-class workflows, confirmed by the user.

## Architecture boundary

```text
React UI
   ↕ typed invoke commands and app events
Tauri Rust boundary
   ↕ versioned JSON Lines over stdin/stdout
Python sidecar
   ├─ SQLite and local files
   ├─ yt-dlp download pipeline
   └─ letras.mus.br lyrics lookup
```

The Python stdout stream is reserved for protocol messages; human-readable logs go to stderr and the local log file. Requests carry an identifier, command, and payload. Responses carry the same identifier. Asynchronous download and library updates are emitted as typed events. Media paths are resolved and checked by the application boundary before the WebView can read them.

## Delivered implementation

- Replaced the PySide6 window, dialogs, widgets, Qt player, and `QThread` download worker with a React/TypeScript frontend and a Qt-free Python sidecar.
- Added a Tauri 2 shell with a restricted backend command list, correlated JSONL requests, asynchronous backend events, and validated local audio paths.
- Implemented library search, favorites, playlist management, metadata, confirmed track and playlist deletion, original/PT-BR lyrics, per-job downloads and retry, a persistent player, and saved settings/themes.
- Preserved the existing SQLite schema and the Windows `Documents/TrackLyrics` library path. Added only the additive lyrics lookup status column.
- Bundled FFmpeg through `imageio-ffmpeg`; `ffprobe` remains optional for best-effort media details.
- Added Windows MSI and NSIS output and ignored generated sidecar/build files.
- Documented the implemented visual system in `DESIGN.md`; `.impeccable/` remains local and ignored.

## Interaction and visual requirements

- Keep all four primary workflows visible and connected in one coherent desktop shell.
- Preserve the relationship between selected track, lyrics, playback queue, active playlist, and download progress.
- Give concurrent download jobs distinct progress and outcome states; a single bar must not misrepresent a parallel queue.
- Distinguish lyrics lookup in progress, no lyrics found, lyrics available, and local file errors.
- Make errors specific to the action and provide a useful next step. Use confirmation before destructive file removal.
- Keep UI copy concise and grounded in real data. Avoid fictional server/network states, placeholder marketing copy, generated artwork, and decorative status panels.
- Use restrained motion for selection, queue updates, and playback feedback. Respect reduced-motion preferences and keyboard focus.

## Direction contract

**THESIS:** TrackLyrics is a local listening archive: every track row is the shared anchor for its library context, lyrics, playback, and actions. The interface avoids generic dashboard cards and fabricated cover art.

**OWN-WORLD:** Build a quiet, information-rich desktop surface from graphite and cool paper neutrals, one restrained audio accent, ruled data columns, a readable lyric field, and a persistent transport. Dark and light themes use the same contrast and hierarchy.

**STORY:** The user moves from a library or playlist to one selected track; its lyrics and player state stay in sync. Downloads and their real per-job states have a dedicated view and remain one action away.

**FIRST VIEWPORT:** At 1440×960, a narrow navigation rail identifies All Tracks, Favorites, playlists, and Downloads; the main track table occupies the center-left; the lyric reader takes a stable right column; search and Add Downloads sit above the active view; the player spans the bottom edge.

**FORM:** Listening Archive, code-led. Its signature interaction is one shared track cursor: selecting or advancing a row updates the lyric reader and player together; live download rows update in place without moving or obscuring playback. This direction translates the user's Apple/Linear quality reference into exact hierarchy and interaction rather than copied branding.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Resolved migration gaps

- Playlist search is scoped to the active playlist in the backend query.
- Each parallel download has its own progress, stage, and outcome.
- Lyrics distinguish lookup pending, no match, failed lookup, and missing local files.
- Deleting the current track stops playback and clears the player before its local folder is removed.
- Track and playlist removal require explicit confirmation; startup does not delete missing records.
- The Windows package includes the Python sidecar and bundled FFmpeg. `ffprobe` is optional.

## Acceptance criteria

- Existing `Documents/TrackLyrics` database, settings, media, and lyrics remain visible after upgrade.
- Every current primary workflow is available and behaves consistently with the active library/playlist context.
- Download events are accurate per job in serial and parallel modes.
- Playback updates the selected track and lyrics and survives seek, volume changes, and queue transitions.
- Destructive operations explain what will be removed and require explicit confirmation.
- No interface text reports a state the application has not measured.
- The app builds as a Tauri desktop artifact with the Python backend bundled and logs separated from IPC.

## Build and review record

- `npm run build` passed: TypeScript and Vite production build.
- `python -m compileall -q src` passed for the Qt-free Python backend.
- `cargo fmt --check` and `cargo check` passed with the development overlay (`externalBin` disabled for source-mode development).
- `npm run tauri:build` produced `TrackLyrics_1.1.0_x64_en-US.msi` and `TrackLyrics_1.1.0_x64-setup.exe` on Windows.
- Visual review covered dark and light at 1440×960 and the compact desktop layout at 1024×680. The workspace contained no library/audio files, so the visual review used an unshipped local fixture; actual playback against a user's library remains device-side behavior.
- English UI copy remains in place. The app continues to use `Documents/TrackLyrics` for the installed Windows build; no migration to Tauri app-data is performed.
