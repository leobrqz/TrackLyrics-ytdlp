use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{Emitter, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::oneshot;

type PendingResponse = oneshot::Sender<Result<Value, String>>;
const ALLOWED_BACKEND_COMMANDS: &[&str] = &[
    "app.bootstrap",
    "library.list",
    "library.get",
    "library.toggleFavorite",
    "library.delete",
    "library.audioSource",
    "playlist.list",
    "playlist.create",
    "playlist.rename",
    "playlist.delete",
    "playlist.addTrack",
    "playlist.removeTrack",
    "downloads.snapshot",
    "downloads.enqueue",
    "settings.get",
    "settings.update",
];

#[derive(Clone)]
struct BackendState {
    child: Arc<Mutex<Option<CommandChild>>>,
    pending: Arc<Mutex<HashMap<String, PendingResponse>>>,
    failure: Arc<Mutex<Option<String>>>,
    request_counter: Arc<AtomicU64>,
    allowed_tracks_root: Arc<PathBuf>,
}

impl BackendState {
    fn new(child: CommandChild, allowed_tracks_root: PathBuf) -> Self {
        Self {
            child: Arc::new(Mutex::new(Some(child))),
            pending: Arc::new(Mutex::new(HashMap::new())),
            failure: Arc::new(Mutex::new(None)),
            request_counter: Arc::new(AtomicU64::new(1)),
            allowed_tracks_root: Arc::new(allowed_tracks_root),
        }
    }

    fn next_id(&self) -> String {
        format!(
            "tauri-{}",
            self.request_counter.fetch_add(1, Ordering::Relaxed)
        )
    }

    async fn request(&self, id: String, command: String, payload: Value) -> Result<Value, String> {
        if let Some(reason) = self
            .failure
            .lock()
            .map_err(|_| "Backend state is unavailable".to_string())?
            .clone()
        {
            return Err(reason);
        }

        let (sender, receiver) = oneshot::channel();
        {
            let mut pending = self
                .pending
                .lock()
                .map_err(|_| "Backend request table is unavailable".to_string())?;
            if pending.contains_key(&id) {
                return Err("Duplicate backend request identifier".into());
            }
            pending.insert(id.clone(), sender);
        }

        let mut line = serde_json::to_vec(&json!({
            "id": id.clone(),
            "command": command,
            "payload": payload,
        }))
        .map_err(|error| format!("Could not encode backend request: {error}"))?;
        line.push(b'\n');

        let write_result = match self.child.lock() {
            Ok(mut child) => match child.as_mut() {
                Some(process) => process
                    .write(&line)
                    .map_err(|error| format!("Could not write to backend: {error}")),
                None => Err("Backend process is not running".to_string()),
            },
            Err(_) => Err("Backend process lock is unavailable".to_string()),
        };

        if let Err(error) = write_result {
            self.remove_pending(&id);
            return Err(error);
        }

        match tokio::time::timeout(Duration::from_secs(120), receiver).await {
            Ok(Ok(Ok(response))) => match response.get("ok").and_then(Value::as_bool) {
                Some(true) => Ok(response.get("data").cloned().unwrap_or(Value::Null)),
                Some(false) => {
                    let error = response.get("error").cloned().unwrap_or(Value::Null);
                    let code = error
                        .get("code")
                        .and_then(Value::as_str)
                        .unwrap_or("backend_error");
                    let message = error
                        .get("message")
                        .and_then(Value::as_str)
                        .unwrap_or("The backend could not complete the action.");
                    Err(format!("{code}: {message}"))
                }
                None => Err("Backend returned a response without an `ok` field".into()),
            },
            Ok(Ok(Err(error))) => Err(error),
            Ok(Err(_)) => Err("Backend response channel closed".into()),
            Err(_) => {
                self.remove_pending(&id);
                Err("Backend request timed out".into())
            }
        }
    }

    fn remove_pending(&self, id: &str) {
        if let Ok(mut pending) = self.pending.lock() {
            pending.remove(id);
        }
    }

    fn validate_audio_source(&self, mut data: Value) -> Result<Value, String> {
        let path = data
            .get("path")
            .and_then(Value::as_str)
            .ok_or_else(|| "Backend returned no media path".to_string())?;
        let candidate = PathBuf::from(path);
        let root = std::fs::canonicalize(self.allowed_tracks_root.as_path())
            .map_err(|error| format!("Could not resolve the track library: {error}"))?;
        let canonical = std::fs::canonicalize(&candidate)
            .map_err(|_| "The audio file is missing from the local library".to_string())?;
        if !canonical.starts_with(&root) || !canonical.is_file() {
            return Err("The requested media file is outside the local track library".into());
        }
        let extension = canonical
            .extension()
            .and_then(|value| value.to_str())
            .unwrap_or_default()
            .to_ascii_lowercase();
        if extension != "mp3" && extension != "wav" {
            return Err("Only MP3 and WAV files can be played".into());
        }
        let Some(object) = data.as_object_mut() else {
            return Err("Backend returned an invalid media path".into());
        };
        object.insert(
            "path".to_string(),
            Value::String(canonical.to_string_lossy().to_string()),
        );
        Ok(data)
    }

    fn fail_pending(&self, reason: &str) {
        if let Ok(mut failure) = self.failure.lock() {
            *failure = Some(reason.to_string());
        }
        if let Ok(mut pending) = self.pending.lock() {
            for (_, sender) in pending.drain() {
                let _ = sender.send(Err(reason.to_string()));
            }
        }
    }

    fn stop(&self) {
        let id = self.next_id();
        let process = self.child.lock().ok().and_then(|mut child| child.take());
        if let Some(mut process) = process {
            let line = format!(
                "{}\n",
                json!({"id": id, "command": "app.shutdown", "payload": {}})
            );
            let _ = process.write(line.as_bytes());
        }
        self.fail_pending("TrackLyrics is closing");
    }
}

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri must be inside the repository")
        .to_path_buf()
}

fn contains_library_data(root: &Path) -> bool {
    if root.join("library.db").is_file() || root.join("app_settings.json").is_file() {
        return true;
    }

    let tracks = root.join("tracks");
    tracks
        .read_dir()
        .ok()
        .and_then(|mut entries| entries.next())
        .is_some()
}

fn resolve_data_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let repo = repository_root();
    let documents = app
        .path()
        .document_dir()
        .map_err(|error| format!("Could not resolve Documents directory: {error}"))?
        .join("TrackLyrics");

    let chosen = if cfg!(debug_assertions) {
        if contains_library_data(&repo) {
            repo
        } else {
            documents
        }
    } else {
        documents
    };

    std::fs::create_dir_all(&chosen)
        .map_err(|error| format!("Could not prepare library directory: {error}"))?;
    Ok(chosen)
}

fn start_backend(app: &tauri::AppHandle) -> Result<(BackendState, PathBuf), String> {
    let repo = repository_root();
    let data_dir = resolve_data_dir(app)?;
    let tracks_root = data_dir.join("tracks");
    std::fs::create_dir_all(&tracks_root)
        .map_err(|error| format!("Could not prepare the track library: {error}"))?;
    let data_dir_string = data_dir.to_string_lossy().to_string();

    let command = if cfg!(debug_assertions) {
        app.shell()
            .command("python")
            .args(["src/sidecar/main.py"])
            .current_dir(repo)
            .env("TRACKLYRICS_DATA_DIR", data_dir_string)
            .set_raw_out(true)
    } else {
        app.shell()
            .sidecar("tracklyrics-backend")
            .map_err(|error| format!("Could not locate the bundled Python backend: {error}"))?
            .env("TRACKLYRICS_DATA_DIR", data_dir_string)
            .set_raw_out(true)
    };

    let (mut events, child) = command
        .spawn()
        .map_err(|error| format!("Could not start the Python backend: {error}"))?;
    let state = BackendState::new(child, tracks_root.clone());
    let reader_state = state.clone();
    let app_handle = app.clone();

    tauri::async_runtime::spawn(async move {
        let mut buffered = Vec::<u8>::new();
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(chunk) => {
                    for byte in chunk {
                        if byte == b'\n' {
                            if buffered.last() == Some(&b'\r') {
                                buffered.pop();
                            }
                            dispatch_protocol_line(&buffered, &reader_state, &app_handle);
                            buffered.clear();
                        } else {
                            buffered.push(byte);
                            if buffered.len() > 8 * 1024 * 1024 {
                                buffered.clear();
                                emit_protocol_error(
                                    &app_handle,
                                    "Backend emitted an oversized protocol line",
                                );
                            }
                        }
                    }
                }
                CommandEvent::Stderr(chunk) => {
                    eprint!("{}", String::from_utf8_lossy(&chunk));
                }
                CommandEvent::Error(error) => {
                    let reason = format!("Backend process error: {error}");
                    reader_state.fail_pending(&reason);
                    emit_protocol_error(&app_handle, &reason);
                }
                CommandEvent::Terminated(_) => {
                    if !buffered.is_empty() {
                        dispatch_protocol_line(&buffered, &reader_state, &app_handle);
                    }
                    let reason = "Python backend stopped".to_string();
                    reader_state.fail_pending(&reason);
                    break;
                }
                _ => {}
            }
        }
    });

    Ok((state, tracks_root))
}

fn dispatch_protocol_line(line: &[u8], state: &BackendState, app: &tauri::AppHandle) {
    if line.is_empty() {
        return;
    }
    let message: Value = match serde_json::from_slice(line) {
        Ok(message) => message,
        Err(error) => {
            emit_protocol_error(app, &format!("Invalid backend protocol message: {error}"));
            return;
        }
    };

    if message.get("event").and_then(Value::as_str).is_some() {
        let _ = app.emit("backend_event", message);
        return;
    }

    let Some(id) = message.get("id").and_then(Value::as_str) else {
        emit_protocol_error(app, "Backend response has no request identifier");
        return;
    };

    if let Ok(mut pending) = state.pending.lock() {
        if let Some(sender) = pending.remove(id) {
            let _ = sender.send(Ok(message));
        }
    }
}

fn emit_protocol_error(app: &tauri::AppHandle, message: &str) {
    let _ = app.emit(
        "backend_event",
        json!({
            "event": "app.error",
            "data": {
                "code": "backend_protocol_error",
                "message": message,
                "hint": "Restart TrackLyrics. If the problem continues, inspect the local app log."
            }
        }),
    );
}

#[tauri::command]
async fn backend_request(
    state: State<'_, BackendState>,
    id: String,
    command: String,
    payload: Value,
) -> Result<Value, String> {
    if id.is_empty() || id.len() > 128 {
        return Err("Backend request identifier is invalid".into());
    }
    if !ALLOWED_BACKEND_COMMANDS.contains(&command.as_str()) {
        return Err("Backend command is not available to the frontend".into());
    }
    let data = state.request(id, command.clone(), payload).await?;
    if command == "library.audioSource" {
        state.validate_audio_source(data)
    } else {
        Ok(data)
    }
}

#[tauri::command]
fn backend_shutdown(state: State<'_, BackendState>) {
    state.stop();
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let (state, tracks_root) =
                start_backend(app.handle()).map_err(std::io::Error::other)?;
            app.asset_protocol_scope()
                .allow_directory(&tracks_root, true)
                .map_err(std::io::Error::other)?;
            app.manage(state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                if let Some(state) = window.try_state::<BackendState>() {
                    state.stop();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![backend_request, backend_shutdown])
        .run(tauri::generate_context!())
        .expect("error while running TrackLyrics");
}
