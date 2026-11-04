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

## Migration sequence

1. **Product and visual direction:** keep `PRODUCT.md` as product truth; establish a code-led design contract and record the final visual system in `DESIGN.md` after implementation review.
2. **Desktop and frontend foundation:** add the Vite/React/TypeScript frontend and Tauri shell, with a small typed bridge and project-owned design tokens.
3. **Sidecar boundary:** split runtime dependencies from Qt UI dependencies; implement versioned JSONL commands/events; detach the worker from `QThread`/Qt signals; keep stdout protocol-safe.
4. **Complete primary interface:** implement library/search/favorites/playlist actions, lyrics states and language switching, persistent playback controls, per-job downloads and errors, settings, and theme persistence.
5. **Data and media compatibility:** preserve the current data root; validate every media path; define handling for missing/corrupt paths and destructive actions; verify seek, volume, end-of-track, and playlist transitions.
6. **Windows packaging:** build and bundle the Tauri app plus Python sidecar. Make FFmpeg/ffprobe availability explicit and ensure the release installer does not silently create a blank library beside the executable.
7. **Review and release handoff:** inspect responsive layouts and desktop interactions, run the Impeccable detector, complete independent finish review, update the design documentation, then commit and push the finished branch.

## Interaction and visual requirements

- Keep all four primary workflows visible and connected in one coherent desktop shell.
- Preserve the relationship between selected track, lyrics, playback queue, active playlist, and download progress.
- Give concurrent download jobs distinct progress and outcome states; a single bar must not misrepresent a parallel queue.
- Distinguish lyrics lookup in progress, no lyrics found, lyrics available, and local file errors.
- Make errors specific to the action and provide a useful next step. Use confirmation before destructive file removal.
- Keep UI copy concise and grounded in real data. Avoid fictional server/network states, placeholder marketing copy, generated artwork, and decorative status panels.
- Use restrained motion for selection, queue updates, and playback feedback. Respect reduced-motion preferences and keyboard focus.

## Known behavior gaps to resolve during the migration

- Searching inside a playlist currently filters all tracks rather than only that playlist.
- Parallel downloads currently share a single progress bar.
- Lyrics unavailable does not distinguish pending lookup from completed lookup with no match.
- Deleting the currently playing track can leave playback pointing at a removed file.
- Startup library validation can offer deletion when folders are missing; preserve records until the user explicitly confirms a destructive action.
- The release workflow does not package FFmpeg/ffprobe, and the current release build is PyInstaller-only.

## Acceptance criteria

- Existing `Documents/TrackLyrics` database, settings, media, and lyrics remain visible after upgrade.
- Every current primary workflow is available and behaves consistently with the active library/playlist context.
- Download events are accurate per job in serial and parallel modes.
- Playback updates the selected track and lyrics and survives seek, volume changes, and queue transitions.
- Destructive operations explain what will be removed and require explicit confirmation.
- No interface text reports a state the application has not measured.
- The app builds as a Tauri desktop artifact with the Python backend bundled and logs separated from IPC.

## Open implementation constraints

- Confirm the final Windows artifact format and FFmpeg redistribution approach before publishing a release.
- Preserve current English UI copy during the first migration; localization can be added as a separate decision.
- Do not move user data into Tauri's default app-data directory without a tested, backed-up migration.
