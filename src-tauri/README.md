# Tauri desktop shell

## Development

From the repository root, run:

```powershell
npm run tauri:dev
```

Tauri starts Vite on `http://localhost:1420`. In debug builds, Rust launches `python src/sidecar/main.py` from the repository root and passes `TRACKLYRICS_DATA_DIR` to the sidecar. Existing repo data is preferred when present; otherwise the sidecar uses `Documents/TrackLyrics`.

## Release build

`tauri build` runs the configured frontend build and then `src-tauri/scripts/build-sidecar.ps1`. The script installs `requirements-backend.txt` and PyInstaller, builds the Python entry point as a console sidecar, and writes `src-tauri/binaries/tracklyrics-backend-<host-target-triple>.exe` for Tauri's external-binary bundler.

The release build must run on the target architecture because PyInstaller bundles the host Python runtime. The sidecar includes the `imageio_ffmpeg` package resources, including its FFmpeg executable; this makes the installer larger, but keeps audio extraction independent of a separate system FFmpeg installation. Generated executables and Rust build output are excluded from Git.

The installed app continues using `Documents/TrackLyrics`. The asset protocol is restricted to `Documents/TrackLyrics/tracks/**`, and Rust also validates that a requested audio path resolves to an existing MP3 or WAV file under the selected track directory before returning it to the frontend.
