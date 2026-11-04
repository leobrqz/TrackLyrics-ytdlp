import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Album,
  ArrowDownToLine,
  AudioLines,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileAudio,
  FileText,
  Heart,
  ListMusic,
  LoaderCircle,
  MoreHorizontal,
  Music2,
  Pause,
  Play,
  Plus,
  Search,
  Settings2,
  SkipBack,
  SkipForward,
  Sun,
  Moon,
  Trash2,
  Volume1,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { backendRequest, listenBackendEvents } from "./lib/backend";
import { formatDate, formatDuration, formatTime, shortUrl } from "./lib/format";
import {
  DEFAULT_SETTINGS,
  normalizeSettings,
  normalizeTrack,
  type AppSettings,
  type BackendEvent,
  type BootstrapData,
  type DownloadJob,
  type EnqueueResult,
  type LibraryView,
  type Lyrics,
  type Playlist,
  type Track,
} from "./lib/types";

type LoadState = "loading" | "ready" | "error";
type PlaylistDialogState = { mode: "create" } | { mode: "rename"; playlist: Playlist } | null;
type ConfirmState = { kind: "track"; track: Track } | { kind: "playlist"; playlist: Playlist } | null;

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "The action could not be completed.";
}

function getTrackId(data: Record<string, unknown>): number | null {
  const value = Number(data.trackId ?? data.id);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function safeFilePath(result: unknown): string {
  if (typeof result === "string") return result;
  if (result && typeof result === "object" && "path" in result && typeof result.path === "string") {
    return result.path;
  }
  throw new Error("The app did not return a valid audio file path.");
}

function viewLabel(view: LibraryView, playlists: Playlist[]): string {
  if (view === "all") return "All tracks";
  if (view === "favorites") return "Favorites";
  if (view === "downloads") return "Downloads";
  const id = Number(view.slice("playlist:".length));
  return playlists.find((playlist) => playlist.id === id)?.name ?? "Playlist";
}

export default function App() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const selectedIdRef = useRef<number | null>(null);
  const trackRequestRef = useRef(0);
  const listRequestRef = useRef(0);
  const playbackQueueRef = useRef<Track[]>([]);
  const settingsRef = useRef<AppSettings>(DEFAULT_SETTINGS);
  const backendEventHandlerRef = useRef<(event: BackendEvent) => void>(() => undefined);

  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [bootError, setBootError] = useState("");
  const [allTracks, setAllTracks] = useState<Track[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [jobs, setJobs] = useState<DownloadJob[]>([]);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [view, setView] = useState<LibraryView>("all");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);
  const [selectedTrackDetails, setSelectedTrackDetails] = useState<Track | null>(null);
  const [detailsLoadingId, setDetailsLoadingId] = useState<number | null>(null);
  const [detailsError, setDetailsError] = useState("");
  const [playerTrackId, setPlayerTrackId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackPosition, setPlaybackPosition] = useState(0);
  const [playbackDuration, setPlaybackDuration] = useState(0);
  const [playerVolume, setPlayerVolume] = useState(DEFAULT_SETTINGS.volume);
  const [queueOpen, setQueueOpen] = useState(false);
  const [lyricsPendingIds, setLyricsPendingIds] = useState<Set<number>>(() => new Set());
  const [lyricsResolvedIds, setLyricsResolvedIds] = useState<Set<number>>(() => new Set());
  const [lyricsLanguage, setLyricsLanguage] = useState<"original" | "ptbr">("original");
  const [downloadsOpen, setDownloadsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [playlistDialog, setPlaylistDialog] = useState<PlaylistDialogState>(null);
  const [metadataTrack, setMetadataTrack] = useState<Track | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const [notice, setNotice] = useState<{ kind: "success" | "error" | "warning"; text: string } | null>(null);
  const [narrowLyricsOpen, setNarrowLyricsOpen] = useState(false);

  const selectedTrackIdValue = selectedTrackId;
  selectedIdRef.current = selectedTrackIdValue;
  settingsRef.current = settings;

  const selectedTrack = useMemo(() => {
    if (selectedTrackDetails?.id === selectedTrackId) return selectedTrackDetails;
    return tracks.find((track) => track.id === selectedTrackId)
      ?? allTracks.find((track) => track.id === selectedTrackId)
      ?? null;
  }, [allTracks, selectedTrackDetails, selectedTrackId, tracks]);

  const playerTrack = useMemo(
    () => allTracks.find((track) => track.id === playerTrackId)
      ?? tracks.find((track) => track.id === playerTrackId)
      ?? (selectedTrack?.id === playerTrackId ? selectedTrack : null),
    [allTracks, playerTrackId, selectedTrack, tracks],
  );

  const pendingCount = jobs.filter((job) => job.status === "pending" || job.status === "running").length;
  const visibleJobs = useMemo(() => {
    const query = appliedSearch.trim().toLocaleLowerCase();
    if (!query) return jobs;
    return jobs.filter((job) => `${job.title ?? ""} ${job.artist ?? ""} ${job.url} ${job.status}`.toLocaleLowerCase().includes(query));
  }, [appliedSearch, jobs]);

  const notify = useCallback((kind: "success" | "error" | "warning", text: string) => {
    setNotice({ kind, text });
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), notice.kind === "error" ? 7200 : 4200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const loadPlaylists = useCallback(async () => {
    const result = await backendRequest<Playlist[]>("playlist.list");
    setPlaylists(Array.isArray(result) ? result : []);
  }, []);

  const loadJobs = useCallback(async () => {
    const result = await backendRequest<DownloadJob[]>("downloads.snapshot");
    setJobs(Array.isArray(result) ? result : []);
  }, []);

  const loadTrackDetails = useCallback(async (trackId: number) => {
    const requestId = ++trackRequestRef.current;
    setDetailsLoadingId(trackId);
    setDetailsError("");
    try {
      const result = await backendRequest<Track>("library.get", { trackId });
      if (requestId !== trackRequestRef.current || selectedIdRef.current !== trackId) return null;
      const track = normalizeTrack(result);
      setSelectedTrackDetails(track);
      setAllTracks((current) => current.map((item) => item.id === track.id ? track : item));
      setTracks((current) => current.map((item) => item.id === track.id ? track : item));
      return track;
    } catch (error) {
      if (requestId === trackRequestRef.current && selectedIdRef.current === trackId) setDetailsError(errorMessage(error));
      throw error;
    } finally {
      if (requestId === trackRequestRef.current) setDetailsLoadingId(null);
    }
  }, []);

  const loadTrackList = useCallback(async (nextView: LibraryView, query: string) => {
    if (nextView === "downloads") return;
    const requestId = ++listRequestRef.current;
    const playlistId = nextView.startsWith("playlist:") ? Number(nextView.slice("playlist:".length)) : null;
    const result = await backendRequest<Track[]>("library.list", {
      playlistId,
      query,
      favoritesOnly: nextView === "favorites",
    });
    if (requestId !== listRequestRef.current) return;
    const nextTracks = Array.isArray(result) ? result.map((track) => normalizeTrack(track)) : [];
    setTracks(nextTracks);
    if (nextView === "all" && !query) setAllTracks(nextTracks);
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadPlaylists(), loadJobs()]);
    await loadTrackList(view, appliedSearch);
  }, [appliedSearch, loadJobs, loadPlaylists, loadTrackList, view]);

  const handleBackendEvent = useCallback((event: BackendEvent) => {
    const data = (event.data ?? {}) as Record<string, unknown>;
    if (event.event === "downloads.progress") {
      const jobId = String(data.jobId ?? "");
      const progress = Math.max(0, Math.min(100, Number(data.progress ?? data.percent ?? 0)));
      setJobs((current) => current.map((job) => job.jobId === jobId ? { ...job, progress } : job));
      return;
    }
    if (event.event === "downloads.status") {
      const jobId = String(data.jobId ?? "");
      const status = String(data.status ?? "pending");
      const stage = typeof data.stage === "string" ? data.stage : undefined;
      const error = typeof data.error === "string" ? data.error : null;
      setJobs((current) => current.map((job) => job.jobId === jobId ? { ...job, status, stage, error, ...(status === "done" ? { progress: 100 } : {}) } : job));
      return;
    }
    if (event.event === "library.track_saved") {
      const id = getTrackId(data);
      if (id !== null) setLyricsPendingIds((current) => new Set(current).add(id));
      void refreshAll().catch((error) => notify("error", errorMessage(error)));
      return;
    }
    if (event.event === "lyrics.ready") {
      const id = getTrackId(data);
      if (id !== null) {
        setLyricsPendingIds((current) => {
          const next = new Set(current);
          next.delete(id);
          return next;
        });
        setLyricsResolvedIds((current) => new Set(current).add(id));
        if (selectedIdRef.current === id) void loadTrackDetails(id).catch((error) => notify("error", errorMessage(error)));
      }
      return;
    }
    if (event.event === "downloads.duplicate") {
      const artist = String(data.artist ?? "");
      const title = String(data.title ?? "");
      notify("warning", `Already in your library: ${[artist, title].filter(Boolean).join(" — ") || "matching track"}. The new copy will still be saved.`);
      return;
    }
    if (event.event === "app.error") {
      const operation = String(data.operation ?? "");
      const message = String(data.message ?? data.reason ?? "The action could not be completed.");
      const hint = String(data.hint ?? "");
      notify("error", [operation, message, hint].filter(Boolean).join(" · "));
    }
  }, [loadTrackDetails, notify, refreshAll]);

  backendEventHandlerRef.current = handleBackendEvent;

  useEffect(() => {
    let mounted = true;
    let unlisten: (() => void) | undefined;

    void (async () => {
      try {
        unlisten = await listenBackendEvents((event) => backendEventHandlerRef.current(event));
        const data = await backendRequest<BootstrapData>("app.bootstrap");
        if (!mounted) return;
        const initialTracks = Array.isArray(data.tracks) ? data.tracks.map((track) => normalizeTrack(track)) : [];
        const initialPlaylists = Array.isArray(data.playlists) ? data.playlists : [];
        const initialJobs = Array.isArray(data.queue) ? data.queue : [];
        const initialSettings = normalizeSettings(data.settings);
        setAllTracks(initialTracks);
        setTracks(initialTracks);
        setPlaylists(initialPlaylists);
        setJobs(initialJobs);
        setSettings(initialSettings);
        setPlayerVolume(initialSettings.volume);
        setLoadState("ready");
        if (audioRef.current) audioRef.current.volume = initialSettings.volume;
      } catch (error) {
        if (!mounted) return;
        setBootError(errorMessage(error));
        setLoadState("error");
      }
    })();

    return () => {
      mounted = false;
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setAppliedSearch(search), 180);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (loadState !== "ready" || view === "downloads") return;
    void loadTrackList(view, appliedSearch).catch((error) => notify("error", errorMessage(error)));
  }, [appliedSearch, loadState, loadTrackList, notify, view]);

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme;
    if (audioRef.current) audioRef.current.volume = playerVolume;
  }, [playerVolume, settings.theme]);

  const chooseView = (nextView: LibraryView) => {
    setView(nextView);
    setSearch("");
    setAppliedSearch("");
    setQueueOpen(false);
    setNarrowLyricsOpen(false);
  };

  const chooseTrack = async (track: Track, queue: Track[]) => {
    setSelectedTrackId(track.id);
    selectedIdRef.current = track.id;
    setSelectedTrackDetails(null);
    setDetailsError("");
    setLyricsLanguage(track.lyrics?.hasOriginal ? "original" : "ptbr");
    setNarrowLyricsOpen(true);
    playbackQueueRef.current = queue;
    try {
      void loadTrackDetails(track.id).catch((error) => notify("error", errorMessage(error)));
      const result = await backendRequest<unknown>("library.audioSource", { trackId: track.id });
      const path = safeFilePath(result);
      const audio = audioRef.current;
      if (!audio) throw new Error("The audio player is not ready.");
      audio.pause();
      audio.src = convertFileSrc(path);
      audio.volume = settingsRef.current.volume;
      audio.load();
      setPlaybackPosition(0);
      setPlaybackDuration(0);
      setPlayerTrackId(track.id);
      await audio.play();
      setIsPlaying(true);
    } catch (error) {
      setIsPlaying(false);
      notify("error", `Could not play ${track.title}: ${errorMessage(error)}`);
    }
  };

  const togglePlayback = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
      return;
    }
    if (audio.src) {
      try {
        await audio.play();
        setIsPlaying(true);
      } catch (error) {
        notify("error", errorMessage(error));
      }
      return;
    }
    const target = selectedTrack ?? tracks[0];
    if (target) await chooseTrack(target, tracks);
  };

  const skipTrack = async (direction: -1 | 1) => {
    const queue = playbackQueueRef.current.length ? playbackQueueRef.current : tracks;
    if (!queue.length) return;
    const currentIndex = queue.findIndex((track) => track.id === playerTrackId);
    const nextIndex = currentIndex < 0 ? (direction > 0 ? 0 : -1) : currentIndex + direction;
    if (nextIndex < 0 || nextIndex >= queue.length) {
      if (direction > 0 && currentIndex === queue.length - 1) {
        audioRef.current?.pause();
        if (audioRef.current) audioRef.current.currentTime = 0;
        setIsPlaying(false);
        setPlaybackPosition(0);
      }
      return;
    }
    await chooseTrack(queue[nextIndex], queue);
  };

  const handleAudioEnded = () => {
    void skipTrack(1);
  };

  const handleAudioError = () => {
    if (playerTrackId !== null) {
      const track = allTracks.find((item) => item.id === playerTrackId);
      notify("error", `The audio file for ${track?.title ?? "this track"} could not be played.`);
    }
    setIsPlaying(false);
  };

  const changeVolume = (value: number) => {
    const volume = Math.max(0, Math.min(1, value));
    setPlayerVolume(volume);
    if (audioRef.current) audioRef.current.volume = volume;
  };

  const persistVolume = () => {
    void backendRequest("settings.update", { values: { volume: Math.round(playerVolume * 100) } }).catch((error) => notify("error", errorMessage(error)));
  };

  const setTheme = (theme: AppSettings["theme"]) => {
    setSettings((current) => ({ ...current, theme }));
    void backendRequest("settings.update", { values: { theme } }).catch((error) => notify("error", errorMessage(error)));
  };

  const saveSettings = async (values: Partial<AppSettings>) => {
    const next = normalizeSettings({ ...settings, ...values });
    const backendValues = { ...values, ...(values.volume !== undefined ? { volume: Math.round(values.volume * 100) } : {}) };
    await backendRequest("settings.update", { values: backendValues });
    setSettings(next);
    setPlayerVolume(next.volume);
    if (audioRef.current) audioRef.current.volume = next.volume;
    notify("success", "Settings saved.");
  };

  const toggleFavorite = async (track: Track) => {
    const favorite = !track.favorite;
    try {
      await backendRequest("library.toggleFavorite", { trackId: track.id, favorite });
      setAllTracks((current) => current.map((item) => item.id === track.id ? { ...item, favorite } : item));
      setTracks((current) => current.map((item) => item.id === track.id ? { ...item, favorite } : item));
      if (selectedTrackDetails?.id === track.id) setSelectedTrackDetails({ ...selectedTrackDetails, favorite });
      if (view === "favorites" && !favorite) setTracks((current) => current.filter((item) => item.id !== track.id));
    } catch (error) {
      notify("error", errorMessage(error));
    }
  };

  const createPlaylist = async (name: string) => {
    await backendRequest("playlist.create", { name });
    await loadPlaylists();
    setPlaylistDialog(null);
    notify("success", `Playlist “${name}” created.`);
  };

  const renamePlaylist = async (playlist: Playlist, name: string) => {
    await backendRequest("playlist.rename", { playlistId: playlist.id, name });
    await loadPlaylists();
    setPlaylistDialog(null);
    if (view === `playlist:${playlist.id}`) setView(`playlist:${playlist.id}`);
    notify("success", `Playlist renamed to “${name}”.`);
  };

  const addToPlaylist = async (playlist: Playlist, track: Track) => {
    try {
      await backendRequest("playlist.addTrack", { playlistId: playlist.id, trackId: track.id });
      await Promise.all([loadPlaylists(), loadTrackList(view, appliedSearch)]);
      notify("success", `Added “${track.title}” to “${playlist.name}”.`);
    } catch (error) {
      notify("error", errorMessage(error));
    }
  };

  const removeFromPlaylist = async (playlistId: number, track: Track) => {
    try {
      await backendRequest("playlist.removeTrack", { playlistId, trackId: track.id });
      await Promise.all([loadPlaylists(), loadTrackList(view, appliedSearch)]);
      notify("success", `Removed “${track.title}” from this playlist.`);
    } catch (error) {
      notify("error", errorMessage(error));
    }
  };

  const deletePlaylist = async (playlist: Playlist) => {
    await backendRequest("playlist.delete", { playlistId: playlist.id });
    if (view === `playlist:${playlist.id}`) chooseView("all");
    await loadPlaylists();
    setConfirmState(null);
    notify("success", `Playlist “${playlist.name}” deleted. Its tracks remain in your library.`);
  };

  const deleteTrack = async (track: Track) => {
    try {
      if (playerTrackId === track.id) {
        audioRef.current?.pause();
        if (audioRef.current) {
          audioRef.current.removeAttribute("src");
          audioRef.current.load();
        }
        setPlayerTrackId(null);
        setIsPlaying(false);
        setPlaybackPosition(0);
        setPlaybackDuration(0);
        playbackQueueRef.current = playbackQueueRef.current.filter((item) => item.id !== track.id);
      }
      await backendRequest("library.delete", { trackId: track.id });
      setAllTracks((current) => current.filter((item) => item.id !== track.id));
      setTracks((current) => current.filter((item) => item.id !== track.id));
      if (selectedTrackId === track.id) {
        setSelectedTrackId(null);
        selectedIdRef.current = null;
        setSelectedTrackDetails(null);
      }
      setConfirmState(null);
      await loadPlaylists();
      notify("success", `“${track.title}” and its local files were removed.`);
    } catch (error) {
      notify("error", errorMessage(error));
    }
  };

  const submitDownloads = async (urls: string[], formatType: "mp3" | "wav") => {
    const result = await backendRequest<EnqueueResult>("downloads.enqueue", { urls, formatType });
    const added = Array.isArray(result?.jobs) ? result.jobs.length : 0;
    const failures = Array.isArray(result?.failedInputs) ? result.failedInputs : [];
    if (added === 0 && failures.length > 0) {
      throw new Error(failures.map((item) => `${shortUrl(item.url)} — ${item.message}`).join("\n"));
    }
    await loadJobs();
    setDownloadsOpen(false);
    setView("downloads");
    setSearch("");
    setAppliedSearch("");
    if (failures.length > 0) {
      notify("warning", `${added} ${added === 1 ? "download was added" : "downloads were added"}; ${failures.length} input${failures.length === 1 ? "" : "s"} could not be queued. ${failures[0].message}`);
    } else {
      notify("success", `${added} ${added === 1 ? "download added" : "downloads added"} to the queue.`);
    }
  };

  const retryJob = async (job: DownloadJob) => {
    const result = await backendRequest<EnqueueResult>("downloads.enqueue", { urls: [job.url], formatType: job.formatType });
    if (!result.jobs.length) throw new Error(result.failedInputs[0]?.message ?? "The URL did not produce a download job.");
    await loadJobs();
    notify("success", "Download added to the queue again.");
  };

  const getActivePlaylistId = view.startsWith("playlist:") ? Number(view.slice("playlist:".length)) : null;
  const pageTitle = viewLabel(view, playlists);
  const currentlyPendingLyrics = selectedTrack ? lyricsPendingIds.has(selectedTrack.id) || selectedTrack.lyrics?.searchStatus === "pending" : false;
  const lyricsAlreadyResolved = selectedTrack ? lyricsResolvedIds.has(selectedTrack.id) || selectedTrack.lyrics?.searchStatus === "complete" : false;

  return (
    <div className="app-frame">
      <audio
        ref={audioRef}
        preload="metadata"
        onTimeUpdate={(event) => setPlaybackPosition(event.currentTarget.currentTime)}
        onDurationChange={(event) => setPlaybackDuration(event.currentTarget.duration || 0)}
        onEnded={handleAudioEnded}
        onError={handleAudioError}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />

      <Sidebar
        view={view}
        playlists={playlists}
        jobsPending={pendingCount}
        trackCount={allTracks.length}
        favoriteCount={allTracks.filter((track) => track.favorite).length}
        onView={chooseView}
        onCreatePlaylist={() => setPlaylistDialog({ mode: "create" })}
        onRenamePlaylist={(playlist) => setPlaylistDialog({ mode: "rename", playlist })}
        onDeletePlaylist={(playlist) => setConfirmState({ kind: "playlist", playlist })}
      />

      <main className="main-stage">
        <header className="topbar">
          <div className="topbar-title">
            <h1>{pageTitle}</h1>
            <span className="topbar-count">
              {view === "downloads" ? `${jobs.length} ${jobs.length === 1 ? "job" : "jobs"}` : `${tracks.length} ${tracks.length === 1 ? "track" : "tracks"}`}
            </span>
          </div>
          <div className="topbar-actions">
            <label className="search-field">
              <Search size={15} aria-hidden="true" />
              <input
                aria-label={view === "downloads" ? "Search downloads" : "Search tracks"}
                placeholder={view === "downloads" ? "Search downloads" : "Search tracks"}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                disabled={loadState !== "ready"}
              />
              {search && <button className="search-clear" type="button" aria-label="Clear search" onClick={() => setSearch("")}><X size={13} /></button>}
            </label>
            <button className="button button-primary" type="button" onClick={() => setDownloadsOpen(true)}>
              <Plus size={15} strokeWidth={2.2} />
              <span>Add downloads</span>
            </button>
            <button
              className="icon-button theme-button"
              type="button"
              aria-label={`Switch to ${settings.theme === "dark" ? "light" : "dark"} appearance`}
              title={`Switch to ${settings.theme === "dark" ? "light" : "dark"} appearance`}
              onClick={() => setTheme(settings.theme === "dark" ? "light" : "dark")}
            >
              {settings.theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button className="icon-button" type="button" aria-label="Settings" title="Settings" onClick={() => setSettingsOpen(true)}>
              <Settings2 size={16} />
            </button>
          </div>
        </header>

        <section className="workspace" aria-label="Track library workspace">
          <div className={`library-column ${narrowLyricsOpen ? "narrow-hidden" : ""}`}>
            {loadState === "loading" ? (
              <LoadingState label="Opening your library" />
            ) : loadState === "error" ? (
              <ErrorState message={bootError} onRetry={() => window.location.reload()} />
            ) : view === "downloads" ? (
              <DownloadsView jobs={visibleJobs} pendingCount={pendingCount} search={appliedSearch} onRetry={retryJob} onAdd={() => setDownloadsOpen(true)} />
            ) : (
              <LibraryView
                tracks={tracks}
                view={view}
                search={appliedSearch}
                selectedTrackId={selectedTrackId}
                playerTrackId={playerTrackId}
                isPlaying={isPlaying}
                playlists={playlists}
                activePlaylistId={getActivePlaylistId}
                onSelect={(track) => void chooseTrack(track, tracks)}
                onFavorite={toggleFavorite}
                onMetadata={setMetadataTrack}
                onDelete={(track) => setConfirmState({ kind: "track", track })}
                onAddToPlaylist={addToPlaylist}
                onRemoveFromPlaylist={removeFromPlaylist}
              />
            )}
          </div>
          <LyricsPanel
            track={selectedTrack}
            language={lyricsLanguage}
            pending={currentlyPendingLyrics}
            lookupResolved={lyricsAlreadyResolved}
            loading={detailsLoadingId === selectedTrackId}
            detailsError={detailsError}
            isNarrowVisible={narrowLyricsOpen}
            onLanguage={setLyricsLanguage}
            onBack={() => setNarrowLyricsOpen(false)}
            onOpenDownloads={() => setDownloadsOpen(true)}
            onRetryDetails={() => {
              if (selectedTrackId !== null) void loadTrackDetails(selectedTrackId).catch((error) => notify("error", errorMessage(error)));
            }}
          />
        </section>

        <PlayerDock
          track={playerTrack}
          isPlaying={isPlaying}
          position={playbackPosition}
          duration={playbackDuration}
          volume={playerVolume}
          queueOpen={queueOpen}
          onToggle={togglePlayback}
          onPrevious={() => void skipTrack(-1)}
          onNext={() => void skipTrack(1)}
          onSeek={(value) => {
            if (audioRef.current && Number.isFinite(value)) audioRef.current.currentTime = value;
          }}
          onVolume={changeVolume}
          onVolumeCommit={persistVolume}
          onToggleQueue={() => setQueueOpen((current) => !current)}
        />

        {queueOpen && (
          <div className="queue-popover" role="region" aria-label="Download queue">
            <DownloadsView jobs={jobs} pendingCount={pendingCount} onRetry={retryJob} onAdd={() => setDownloadsOpen(true)} compact />
          </div>
        )}
      </main>

      {notice && <Notice notice={notice} onDismiss={() => setNotice(null)} />}

      <AddDownloadsDialog open={downloadsOpen} onOpenChange={setDownloadsOpen} onSubmit={submitDownloads} />
      <PlaylistDialog
        state={playlistDialog}
        onOpenChange={(open) => { if (!open) setPlaylistDialog(null); }}
        onCreate={createPlaylist}
        onRename={renamePlaylist}
      />
      <SettingsDialog open={settingsOpen} settings={settings} onOpenChange={setSettingsOpen} onSave={saveSettings} />
      <MetadataDialog track={metadataTrack} onOpenChange={(open) => { if (!open) setMetadataTrack(null); }} />
      <ConfirmDialog
        state={confirmState}
        onOpenChange={(open) => { if (!open) setConfirmState(null); }}
        onConfirm={() => {
          if (!confirmState) return;
          if (confirmState.kind === "track") void deleteTrack(confirmState.track);
          else void deletePlaylist(confirmState.playlist);
        }}
      />
    </div>
  );
}

function Sidebar({
  view,
  playlists,
  jobsPending,
  trackCount,
  favoriteCount,
  onView,
  onCreatePlaylist,
  onRenamePlaylist,
  onDeletePlaylist,
}: {
  view: LibraryView;
  playlists: Playlist[];
  jobsPending: number;
  trackCount: number;
  favoriteCount: number;
  onView: (view: LibraryView) => void;
  onCreatePlaylist: () => void;
  onRenamePlaylist: (playlist: Playlist) => void;
  onDeletePlaylist: (playlist: Playlist) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true"><AudioLines size={18} strokeWidth={2.2} /></div>
        <div className="brand-name">Track<span>Lyrics</span></div>
      </div>

      <nav className="primary-nav" aria-label="Primary navigation">
        <NavButton icon={<Album size={16} />} label="All tracks" active={view === "all"} count={trackCount} onClick={() => onView("all")} />
        <NavButton icon={<Heart size={16} />} label="Favorites" active={view === "favorites"} count={favoriteCount} onClick={() => onView("favorites")} />
        <NavButton icon={<ArrowDownToLine size={16} />} label="Downloads" active={view === "downloads"} count={jobsPending} onClick={() => onView("downloads")} />
      </nav>

      <div className="sidebar-divider" />
      <div className="sidebar-section-heading">
        <span>Playlists</span>
        <button className="sidebar-add" type="button" aria-label="Create playlist" title="Create playlist" onClick={onCreatePlaylist}><Plus size={15} /></button>
      </div>
      <nav className="playlist-nav" aria-label="Playlists">
        {playlists.length === 0 ? (
          <button className="playlist-empty" type="button" onClick={onCreatePlaylist}>Create your first playlist</button>
        ) : playlists.map((playlist) => (
          <div className={`playlist-nav-row ${view === `playlist:${playlist.id}` ? "is-active" : ""}`} key={playlist.id}>
            <button className="playlist-nav-button" type="button" onClick={() => onView(`playlist:${playlist.id}`)}>
              <ListMusic size={15} />
              <span className="playlist-nav-name">{playlist.name}</span>
              {typeof playlist.trackCount === "number" && <span className="playlist-count">{playlist.trackCount}</span>}
            </button>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="playlist-more" type="button" aria-label={`Playlist options for ${playlist.name}`}><MoreHorizontal size={15} /></button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content className="menu-content" sideOffset={5} align="end">
                  <DropdownMenu.Item className="menu-item" onSelect={() => onRenamePlaylist(playlist)}>Rename playlist</DropdownMenu.Item>
                  <DropdownMenu.Separator className="menu-separator" />
                  <DropdownMenu.Item className="menu-item danger-item" onSelect={() => onDeletePlaylist(playlist)}>Delete playlist</DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        ))}
      </nav>

      <div className="sidebar-spacer" />
      <div className="sidebar-footnote">
        <span className="local-indicator" aria-hidden="true" />
        <span>Your library stays on this device</span>
      </div>
    </aside>
  );
}

function NavButton({ icon, label, active, count, onClick }: { icon: React.ReactNode; label: string; active: boolean; count: number; onClick: () => void }) {
  return (
    <button className={`nav-button ${active ? "is-active" : ""}`} type="button" aria-current={active ? "page" : undefined} onClick={onClick}>
      <span className="nav-icon">{icon}</span>
      <span className="nav-label">{label}</span>
      <span className="nav-count">{count}</span>
    </button>
  );
}

function LibraryView({
  tracks,
  view,
  search,
  selectedTrackId,
  playerTrackId,
  isPlaying,
  playlists,
  activePlaylistId,
  onSelect,
  onFavorite,
  onMetadata,
  onDelete,
  onAddToPlaylist,
  onRemoveFromPlaylist,
}: {
  tracks: Track[];
  view: LibraryView;
  search: string;
  selectedTrackId: number | null;
  playerTrackId: number | null;
  isPlaying: boolean;
  playlists: Playlist[];
  activePlaylistId: number | null;
  onSelect: (track: Track) => void;
  onFavorite: (track: Track) => void;
  onMetadata: (track: Track) => void;
  onDelete: (track: Track) => void;
  onAddToPlaylist: (playlist: Playlist, track: Track) => void;
  onRemoveFromPlaylist: (playlistId: number, track: Track) => void;
}) {
  return (
    <div className="library-view">
      <div className="list-toolbar">
        <div className="list-toolbar-copy">
          <span className="list-toolbar-title">{view === "favorites" ? "Saved for later" : view.startsWith("playlist:") ? "Playlist tracks" : "Your collection"}</span>
          <span className="list-toolbar-subtitle">{tracks.length === 1 ? "1 track" : `${tracks.length} tracks`}</span>
        </div>
        <div className="list-toolbar-tools">
          <span className="column-label">TITLE</span>
          <span className="column-label duration-label">TIME</span>
        </div>
      </div>

      {tracks.length === 0 ? (
        <EmptyLibrary view={view} search={search} />
      ) : (
        <div className="track-table-scroll">
          <table className="track-table">
            <thead className="sr-only">
              <tr><th scope="col">Track</th><th scope="col">Format</th><th scope="col">Duration</th><th scope="col">Actions</th></tr>
            </thead>
            <tbody>
              {tracks.map((track) => {
                const active = selectedTrackId === track.id;
                const current = playerTrackId === track.id;
                const format = track.mediaFiles.find((file) => file.hasAudio)?.formatType ?? track.mediaFiles[0]?.formatType ?? "";
                return (
                  <tr
                    key={track.id}
                    className={`track-row ${active ? "is-selected" : ""} ${current ? "is-current" : ""}`}
                    tabIndex={0}
                    aria-selected={active}
                    onClick={() => onSelect(track)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelect(track);
                      }
                    }}
                  >
                    <td className="track-main-cell">
                      <span className={`row-play-state ${current && isPlaying ? "is-playing" : ""}`} aria-hidden="true">
                        {current && isPlaying ? <AudioLines size={15} /> : active ? <Play size={14} fill="currentColor" /> : <span className="row-index">{String(tracks.indexOf(track) + 1).padStart(2, "0")}</span>}
                      </span>
                      <span className="track-copy">
                        <span className="track-title" title={track.title}>{track.title}</span>
                        <span className="track-artist" title={track.artist}>{track.artist || "Unknown artist"}</span>
                      </span>
                    </td>
                    <td className="track-format-cell">
                      {format ? <span className="format-label">{format.toUpperCase()}</span> : <span className="format-empty">—</span>}
                    </td>
                    <td className="track-duration-cell">{formatDuration(track.duration)}</td>
                    <td className="track-actions-cell" onClick={(event) => event.stopPropagation()}>
                      <button
                        className={`row-icon-button favorite-button ${track.favorite ? "is-favorite" : ""}`}
                        type="button"
                        aria-label={track.favorite ? `Remove ${track.title} from favorites` : `Add ${track.title} to favorites`}
                        title={track.favorite ? "Remove from favorites" : "Add to favorites"}
                        onClick={() => onFavorite(track)}
                      >
                        <Heart size={15} fill={track.favorite ? "currentColor" : "none"} />
                      </button>
                      <TrackMenu
                        track={track}
                        playlists={playlists}
                        activePlaylistId={activePlaylistId}
                        onAddToPlaylist={onAddToPlaylist}
                        onRemoveFromPlaylist={onRemoveFromPlaylist}
                        onMetadata={onMetadata}
                        onDelete={onDelete}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {tracks.length > 0 && (
        <div className="list-footer">
          <span>{view === "all" ? "Library order" : "Current view order"}</span>
          <span>Click a track to play</span>
        </div>
      )}
    </div>
  );
}

function EmptyLibrary({ view, search }: { view: LibraryView; search: string }) {
  if (search) {
    return <div className="empty-state"><div className="empty-symbol"><Search size={18} /></div><h2>No tracks found</h2><p>Try a different artist or title.</p></div>;
  }
  if (view === "favorites") {
    return <div className="empty-state"><div className="empty-symbol"><Heart size={18} /></div><h2>No favorites yet</h2><p>Use the heart on a track to keep it here.</p></div>;
  }
  if (view.startsWith("playlist:")) {
    return <div className="empty-state"><div className="empty-symbol"><ListMusic size={18} /></div><h2>This playlist is empty</h2><p>Add tracks from your collection using the track menu.</p></div>;
  }
  return <div className="empty-state"><div className="empty-symbol"><Music2 size={18} /></div><h2>Your collection is ready</h2><p>Add a YouTube link to bring a track into your local library.</p></div>;
}

function TrackMenu({ track, playlists, activePlaylistId, onAddToPlaylist, onRemoveFromPlaylist, onMetadata, onDelete }: {
  track: Track;
  playlists: Playlist[];
  activePlaylistId: number | null;
  onAddToPlaylist: (playlist: Playlist, track: Track) => void;
  onRemoveFromPlaylist: (playlistId: number, track: Track) => void;
  onMetadata: (track: Track) => void;
  onDelete: (track: Track) => void;
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button className="row-icon-button more-button" type="button" aria-label={`More actions for ${track.title}`} title="More actions"><MoreHorizontal size={16} /></button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="menu-content" sideOffset={5} align="end">
          {playlists.length > 0 && (
            <DropdownMenu.Sub>
              <DropdownMenu.SubTrigger className="menu-item submenu-trigger">Add to playlist<ChevronRight size={14} /></DropdownMenu.SubTrigger>
              <DropdownMenu.Portal>
                <DropdownMenu.SubContent className="menu-content" sideOffset={6} alignOffset={-4}>
                  {playlists.map((playlist) => <DropdownMenu.Item className="menu-item" key={playlist.id} onSelect={() => onAddToPlaylist(playlist, track)}>{playlist.name}</DropdownMenu.Item>)}
                </DropdownMenu.SubContent>
              </DropdownMenu.Portal>
            </DropdownMenu.Sub>
          )}
          {activePlaylistId !== null && <DropdownMenu.Item className="menu-item" onSelect={() => onRemoveFromPlaylist(activePlaylistId, track)}>Remove from this playlist</DropdownMenu.Item>}
          <DropdownMenu.Item className="menu-item" onSelect={() => onMetadata(track)}>View metadata</DropdownMenu.Item>
          <DropdownMenu.Separator className="menu-separator" />
          <DropdownMenu.Item className="menu-item danger-item" onSelect={() => onDelete(track)}>Delete track and files</DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function LyricsPanel({ track, language, pending, lookupResolved, loading, detailsError, isNarrowVisible, onLanguage, onBack, onOpenDownloads, onRetryDetails }: {
  track: Track | null;
  language: "original" | "ptbr";
  pending: boolean;
  lookupResolved: boolean;
  loading: boolean;
  detailsError: string;
  isNarrowVisible: boolean;
  onLanguage: (language: "original" | "ptbr") => void;
  onBack: () => void;
  onOpenDownloads: () => void;
  onRetryDetails: () => void;
}) {
  const lyrics: Lyrics | null = track?.lyrics ?? null;
  const originalAvailable = Boolean(lyrics?.hasOriginal && lyrics.originalText);
  const ptbrAvailable = Boolean(lyrics?.hasPtbr && lyrics.ptbrText);
  const originalStored = Boolean(lyrics?.hasOriginal);
  const ptbrStored = Boolean(lyrics?.hasPtbr);
  const activeAvailable = language === "original" ? originalAvailable : ptbrAvailable;
  const text = language === "original" ? lyrics?.originalText : lyrics?.ptbrText;
  const activeStored = language === "original" ? originalStored : ptbrStored;
  const hasAny = originalStored || ptbrStored;

  useEffect(() => {
    if (language === "original" && !originalAvailable && ptbrAvailable) onLanguage("ptbr");
    else if (language === "ptbr" && !ptbrAvailable && originalAvailable) onLanguage("original");
  }, [language, onLanguage, originalAvailable, ptbrAvailable]);

  return (
    <aside className={`lyrics-column ${isNarrowVisible ? "is-narrow-visible" : ""}`} aria-label="Lyrics">
      <div className="lyrics-header">
        <button className="narrow-back icon-button" type="button" aria-label="Back to library" onClick={onBack}><ChevronLeft size={17} /></button>
        <div className="lyrics-heading">
          <h2>Lyrics</h2>
          {track && <span className="lyrics-track-title" title={track.title}>{track.title}</span>}
        </div>
        {track && hasAny && (
          <div className="language-switch" role="tablist" aria-label="Lyrics language">
            <button type="button" role="tab" aria-selected={language === "original"} className={language === "original" ? "is-active" : ""} onClick={() => onLanguage("original")} disabled={!originalStored}>Original</button>
            <button type="button" role="tab" aria-selected={language === "ptbr"} className={language === "ptbr" ? "is-active" : ""} onClick={() => onLanguage("ptbr")} disabled={!ptbrStored}>PT-BR</button>
          </div>
        )}
      </div>

      {!track ? (
        <div className="lyrics-empty-state">
          <div className="lyrics-rule" />
          <FileText size={19} strokeWidth={1.6} />
          <p>Select a track to read its lyrics.</p>
        </div>
      ) : loading ? (
        <div className="lyrics-empty-state"><LoaderCircle size={18} className="spin" /><p>Opening lyrics…</p></div>
      ) : detailsError ? (
        <div className="lyrics-empty-state"><CircleAlert size={18} /><p>Could not load track details.</p><span>{detailsError}</span><button className="text-button" type="button" onClick={onRetryDetails}>Try again</button></div>
      ) : activeAvailable ? (
        <article className="lyrics-reading" aria-label={`${language === "original" ? "Original" : "Portuguese"} lyrics for ${track.title}`}>
          <div className="lyrics-reading-meta">
            <span>{language === "original" ? "ORIGINAL LYRICS" : "PORTUGUESE TRANSLATION"}</span>
            {language === "ptbr" && lyrics?.ptbrUrl && <a href={lyrics.ptbrUrl} target="_blank" rel="noreferrer" title="Open lyrics source"><ArrowDownToLine size={13} /></a>}
          </div>
          <div className="lyrics-body">{text}</div>
        </article>
      ) : activeStored ? (
        <div className="lyrics-empty-state"><CircleAlert size={18} /><p>The lyrics file is missing.</p><span>The library record points to a file that could not be read.</span></div>
      ) : pending ? (
        <div className="lyrics-empty-state"><LoaderCircle size={18} className="spin" /><p>Looking for lyrics for this track.</p><span>This can finish after playback starts.</span></div>
      ) : lyrics?.searchStatus === "failed" ? (
        <div className="lyrics-empty-state"><CircleAlert size={18} /><p>Lyrics lookup could not complete.</p><span>The track is saved and playback is available.</span></div>
      ) : lookupResolved || lyrics?.searchStatus === "complete" ? (
        <div className="lyrics-empty-state"><FileText size={18} /><p>No lyrics found for this track.</p><span>The lookup finished without finding a match.</span></div>
      ) : (
        <div className="lyrics-empty-state"><FileText size={18} /><p>No lyrics are stored for this track yet.</p><span>Lyrics are checked after a download is added.</span><button className="text-button" type="button" onClick={onOpenDownloads}>Add a download</button></div>
      )}

      {track && lyrics?.originalUrl && (
        <div className="lyrics-source"><span>Source</span><a href={language === "ptbr" ? lyrics.ptbrUrl ?? lyrics.originalUrl : lyrics.originalUrl} target="_blank" rel="noreferrer">letras.mus.br <ArrowDownToLine size={12} /></a></div>
      )}
    </aside>
  );
}

function DownloadsView({ jobs, pendingCount, search = "", onRetry, onAdd, compact = false }: { jobs: DownloadJob[]; pendingCount: number; search?: string; onRetry: (job: DownloadJob) => void; onAdd: () => void; compact?: boolean }) {
  return (
    <div className={`downloads-view ${compact ? "is-compact" : ""}`}>
      <div className="downloads-toolbar">
        <div>
          <h2>{compact ? "Queue" : "Download queue"}</h2>
          <p>{pendingCount === 0 ? "No active downloads" : `${pendingCount} ${pendingCount === 1 ? "job" : "jobs"} in progress`}</p>
        </div>
        {!compact && <button className="button button-secondary" type="button" onClick={onAdd}><Plus size={14} /> Add downloads</button>}
        {compact && <button className="icon-button" type="button" aria-label="Add downloads" onClick={onAdd}><Plus size={15} /></button>}
      </div>
      {jobs.length === 0 ? (
        <div className="downloads-empty"><ArrowDownToLine size={18} /><p>{search ? "No matching downloads." : "Your download queue is empty."}</p>{search ? <span>Try another URL or status.</span> : <button className="text-button" type="button" onClick={onAdd}>Add YouTube links</button>}</div>
      ) : (
        <div className="download-job-list" role="list">
          {jobs.map((job) => <DownloadJobRow key={job.jobId} job={job} onRetry={onRetry} />)}
        </div>
      )}
    </div>
  );
}

function DownloadJobRow({ job, onRetry }: { job: DownloadJob; onRetry: (job: DownloadJob) => void }) {
  const statusLabel = job.status === "pending" ? "Queued" : job.status === "running" ? job.stage ?? "In progress" : job.status === "done" ? "Complete" : job.status === "failed" ? "Failed" : String(job.status);
  const percent = Math.max(0, Math.min(100, Number(job.progress ?? 0)));
  const running = job.status === "running";
  return (
    <div className={`download-job-row ${job.status === "failed" ? "is-failed" : ""}`} role="listitem">
      <div className="job-leading-icon" aria-hidden="true">{running ? <LoaderCircle size={15} className="spin" /> : job.status === "done" ? <Check size={15} /> : job.status === "failed" ? <CircleAlert size={15} /> : <Clock3 size={15} />}</div>
      <div className="job-content">
        <div className="job-title-line">
          <span className="job-title" title={job.title ?? job.url}>{job.title || shortUrl(job.url)}</span>
          <span className="format-label job-format">{job.formatType.toUpperCase()}</span>
        </div>
        <div className="job-status-line">
          <span className={`job-status status-${job.status}`}>{statusLabel}</span>
          {running && <span className="job-percent">{percent}%</span>}
          {job.status === "failed" && job.error && <span className="job-error" title={job.error}>{job.error}</span>}
        </div>
        {(running || job.status === "pending") && <div className="job-progress-track" role="progressbar" aria-label={`Download progress for ${job.title || shortUrl(job.url)}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={running ? percent : 0}><span style={{ transform: `scaleX(${(running ? percent : 0) / 100})` }} /></div>}
      </div>
      {job.status === "failed" && <button className="text-button job-retry" type="button" onClick={() => { void onRetry(job); }}>Retry</button>}
    </div>
  );
}

function PlayerDock({ track, isPlaying, position, duration, volume, queueOpen, onToggle, onPrevious, onNext, onSeek, onVolume, onVolumeCommit, onToggleQueue }: {
  track: Track | null;
  isPlaying: boolean;
  position: number;
  duration: number;
  volume: number;
  queueOpen: boolean;
  onToggle: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onSeek: (value: number) => void;
  onVolume: (value: number) => void;
  onVolumeCommit: () => void;
  onToggleQueue: () => void;
}) {
  const mediaDuration = Number.isFinite(duration) && duration > 0 ? duration : 0;
  const storedDuration = track && Number.isFinite(track.duration) && track.duration > 0 ? track.duration : 0;
  const displayDuration = mediaDuration || storedDuration;
  const canSeek = mediaDuration > 0;
  const clampedPosition = Math.max(0, Math.min(position, displayDuration));
  const volumeIcon = volume === 0 ? <VolumeX size={16} /> : volume < 0.45 ? <Volume1 size={16} /> : <Volume2 size={16} />;
  return (
    <footer className="player-dock" aria-label="Audio player">
      <div className="player-track">
        <div className={`player-track-mark ${isPlaying ? "is-playing" : ""}`} aria-hidden="true"><AudioLines size={17} /></div>
        <div className="player-track-copy">
          <span className="player-track-title">{track?.title ?? "Nothing playing"}</span>
          <span className="player-track-artist">{track?.artist || (track ? "Unknown artist" : "Select a track from your library.")}</span>
        </div>
      </div>

      <div className="player-controls">
        <div className="transport-buttons">
          <button className="transport-button secondary-transport" type="button" aria-label="Previous track" disabled={!track} onClick={onPrevious}><SkipBack size={16} fill="currentColor" /></button>
          <button className="transport-button play-button" type="button" aria-label={isPlaying ? "Pause" : "Play"} disabled={!track} onClick={onToggle}>{isPlaying ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}</button>
          <button className="transport-button secondary-transport" type="button" aria-label="Next track" disabled={!track} onClick={onNext}><SkipForward size={16} fill="currentColor" /></button>
        </div>
        <div className="player-timeline">
          <span className="timeline-time">{formatTime(clampedPosition)}</span>
          <input
            className="range-input seek-input"
            type="range"
            aria-label="Seek"
            min={0}
            max={canSeek ? duration : 0}
            step={0.1}
            value={canSeek ? clampedPosition : 0}
            disabled={!canSeek}
            style={{ "--range-value": `${canSeek ? (clampedPosition / duration) * 100 : 0}%` } as React.CSSProperties}
            onChange={(event) => onSeek(Number(event.target.value))}
          />
          <span className="timeline-time">{displayDuration > 0 ? formatTime(displayDuration) : "—"}</span>
        </div>
      </div>

      <div className="player-tools">
        {track?.mediaFiles?.[0] && <span className="player-format">{track.mediaFiles[0].formatType.toUpperCase()}</span>}
        <div className="volume-control">
          <span aria-hidden="true">{volumeIcon}</span>
          <input
            className="range-input volume-input"
            type="range"
            aria-label="Volume"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            style={{ "--range-value": `${volume * 100}%` } as React.CSSProperties}
            onChange={(event) => onVolume(Number(event.target.value))}
            onPointerUp={onVolumeCommit}
            onKeyUp={onVolumeCommit}
          />
        </div>
        <button className={`icon-button queue-toggle ${queueOpen ? "is-active" : ""}`} type="button" aria-label="Toggle download queue" title="Download queue" aria-pressed={queueOpen} onClick={onToggleQueue}><ListMusic size={17} /></button>
      </div>
    </footer>
  );
}

function Notice({ notice, onDismiss }: { notice: { kind: "success" | "error" | "warning"; text: string }; onDismiss: () => void }) {
  return (
    <div className={`notice notice-${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>
      {notice.kind === "error" ? <CircleAlert size={16} /> : notice.kind === "warning" ? <CircleAlert size={16} /> : <Check size={16} />}
      <span>{notice.text}</span>
      <button className="notice-dismiss" type="button" aria-label="Dismiss notification" onClick={onDismiss}><X size={14} /></button>
    </div>
  );
}

function LoadingState({ label }: { label: string }) {
  return <div className="full-state"><LoaderCircle size={19} className="spin" /><span>{label}</span></div>;
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="full-state error-state"><CircleAlert size={20} /><h2>Could not open TrackLyrics</h2><p>{message}</p><button className="button button-secondary" type="button" onClick={onRetry}>Try again</button></div>;
}

function DialogFrame({ open, onOpenChange, title, description, children, className = "" }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className={`dialog-content ${className}`}>
          <div className="dialog-header">
            <div>
              <Dialog.Title className="dialog-title">{title}</Dialog.Title>
              {description && <Dialog.Description className="dialog-description">{description}</Dialog.Description>}
            </div>
            <Dialog.Close asChild><button className="icon-button dialog-close" type="button" aria-label="Close"><X size={16} /></button></Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function AddDownloadsDialog({ open, onOpenChange, onSubmit }: { open: boolean; onOpenChange: (open: boolean) => void; onSubmit: (urls: string[], format: "mp3" | "wav") => Promise<void> }) {
  const [rawUrls, setRawUrls] = useState("");
  const [format, setFormat] = useState<"mp3" | "wav">("mp3");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const urls = rawUrls.split(/\r?\n/).map((url) => url.trim()).filter(Boolean);

  useEffect(() => {
    if (open) {
      setRawUrls("");
      setError("");
      setSubmitting(false);
    }
  }, [open]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!urls.length || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await onSubmit(urls, format);
      setRawUrls("");
    } catch (error) {
      setError(errorMessage(error));
      setSubmitting(false);
    }
  };

  return (
    <DialogFrame open={open} onOpenChange={onOpenChange} title="Add downloads" description="Paste one YouTube video or playlist link per line." className="download-dialog">
      <form className="dialog-form" onSubmit={submit}>
        <label className="field-label" htmlFor="download-urls">YouTube links</label>
        <textarea
          id="download-urls"
          className="text-area"
          autoFocus
          rows={5}
          placeholder="https://www.youtube.com/watch?v=…"
          value={rawUrls}
          onChange={(event) => setRawUrls(event.target.value)}
          disabled={submitting}
        />
        <div className="field-hint-row"><span>Video and playlist URLs are supported.</span><span>{urls.length || "No"} {urls.length === 1 ? "link" : "links"}</span></div>
        <fieldset className="format-fieldset">
          <legend className="field-label">Audio format</legend>
          <div className="format-choice-group">
            <button className={`format-choice ${format === "mp3" ? "is-active" : ""}`} type="button" aria-pressed={format === "mp3"} onClick={() => setFormat("mp3")}>
              <FileAudio size={16} /><span><strong>MP3</strong><small>192 kbps</small></span>{format === "mp3" && <Check size={15} className="choice-check" />}
            </button>
            <button className={`format-choice ${format === "wav" ? "is-active" : ""}`} type="button" aria-pressed={format === "wav"} onClick={() => setFormat("wav")}>
              <FileAudio size={16} /><span><strong>WAV</strong><small>Uncompressed</small></span>{format === "wav" && <Check size={15} className="choice-check" />}
            </button>
          </div>
        </fieldset>
        {error && <div className="inline-error" role="alert"><CircleAlert size={15} />{error}</div>}
        <div className="dialog-footer">
          <Dialog.Close asChild><button className="button button-quiet" type="button" disabled={submitting}>Cancel</button></Dialog.Close>
          <button className="button button-primary" type="submit" disabled={!urls.length || submitting}>
            {submitting ? <LoaderCircle size={15} className="spin" /> : <ArrowDownToLine size={15} />}
            {submitting ? "Adding…" : `Add ${urls.length || ""} ${urls.length === 1 ? "download" : "downloads"}`}
          </button>
        </div>
      </form>
    </DialogFrame>
  );
}

function PlaylistDialog({ state, onOpenChange, onCreate, onRename }: {
  state: PlaylistDialogState;
  onOpenChange: (open: boolean) => void;
  onCreate: (name: string) => Promise<void>;
  onRename: (playlist: Playlist, name: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (state) {
      setName(state.mode === "rename" ? state.playlist.name : "");
      setError("");
      setSaving(false);
    }
  }, [state]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const clean = name.trim();
    if (!clean || !state) return;
    setSaving(true);
    setError("");
    try {
      if (state.mode === "create") await onCreate(clean);
      else await onRename(state.playlist, clean);
    } catch (error) {
      setError(errorMessage(error));
      setSaving(false);
    }
  };

  return (
    <DialogFrame open={Boolean(state)} onOpenChange={onOpenChange} title={state?.mode === "rename" ? "Rename playlist" : "New playlist"} description={state?.mode === "rename" ? "Choose a name that helps you find it again." : "Keep a set of tracks together in your library."}>
      <form className="dialog-form" onSubmit={submit}>
        <label className="field-label" htmlFor="playlist-name">Playlist name</label>
        <input id="playlist-name" className="text-input" autoFocus value={name} maxLength={80} onChange={(event) => setName(event.target.value)} disabled={saving} />
        {error && <div className="inline-error" role="alert"><CircleAlert size={15} />{error}</div>}
        <div className="dialog-footer">
          <Dialog.Close asChild><button className="button button-quiet" type="button" disabled={saving}>Cancel</button></Dialog.Close>
          <button className="button button-primary" type="submit" disabled={!name.trim() || saving}>{saving ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />}{state?.mode === "rename" ? "Save name" : "Create playlist"}</button>
        </div>
      </form>
    </DialogFrame>
  );
}

function SettingsDialog({ open, settings, onOpenChange, onSave }: { open: boolean; settings: AppSettings; onOpenChange: (open: boolean) => void; onSave: (values: Partial<AppSettings>) => Promise<void> }) {
  const [draft, setDraft] = useState(settings);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (open) { setDraft(settings); setError(""); } }, [open, settings]);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await onSave(draft);
      onOpenChange(false);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogFrame open={open} onOpenChange={onOpenChange} title="Settings" description="Adjust how downloads and lyrics are processed.">
      <div className="settings-form">
        <div className="settings-row">
          <div className="settings-copy"><strong>Appearance</strong><span>Choose the library surface.</span></div>
          <div className="segmented-control" role="group" aria-label="Appearance">
            <button type="button" className={draft.theme === "dark" ? "is-active" : ""} aria-pressed={draft.theme === "dark"} onClick={() => setDraft({ ...draft, theme: "dark" })}><Moon size={14} />Dark</button>
            <button type="button" className={draft.theme === "light" ? "is-active" : ""} aria-pressed={draft.theme === "light"} onClick={() => setDraft({ ...draft, theme: "light" })}><Sun size={14} />Light</button>
          </div>
        </div>
        <div className="settings-row">
          <div className="settings-copy"><strong>Download order</strong><span>Process one job at a time or in parallel.</span></div>
          <select className="select-input" value={draft.downloadQueueMode} onChange={(event) => setDraft({ ...draft, downloadQueueMode: event.target.value as AppSettings["downloadQueueMode"] })} aria-label="Download order">
            <option value="fifo">One at a time</option><option value="parallel">Parallel</option>
          </select>
        </div>
        {draft.downloadQueueMode === "parallel" && (
          <div className="settings-row settings-row-nested">
            <div className="settings-copy"><strong>Concurrent downloads</strong><span>Maximum active jobs.</span></div>
            <select className="select-input select-small" value={draft.downloadParallelWorkers} onChange={(event) => setDraft({ ...draft, downloadParallelWorkers: Number(event.target.value) })} aria-label="Concurrent downloads">
              {[2, 3, 4, 5, 6, 7, 8].map((number) => <option key={number} value={number}>{number}</option>)}
            </select>
          </div>
        )}
        <div className="settings-row">
          <div className="settings-copy"><strong>Search lyrics alongside downloads</strong><span>Use parallel lookup when several tracks are added.</span></div>
          <button className={`switch ${draft.lyricsParallelWithDownload ? "is-on" : ""}`} type="button" role="switch" aria-checked={draft.lyricsParallelWithDownload} onClick={() => setDraft({ ...draft, lyricsParallelWithDownload: !draft.lyricsParallelWithDownload })}><span /></button>
        </div>
        {error && <div className="inline-error" role="alert"><CircleAlert size={15} />{error}</div>}
        <div className="dialog-footer settings-footer">
          <Dialog.Close asChild><button className="button button-quiet" type="button" disabled={saving}>Cancel</button></Dialog.Close>
          <button className="button button-primary" type="button" disabled={saving} onClick={() => void save()}>{saving ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />}Save settings</button>
        </div>
      </div>
    </DialogFrame>
  );
}

function MetadataDialog({ track, onOpenChange }: { track: Track | null; onOpenChange: (open: boolean) => void }) {
  const media = track?.mediaFiles ?? [];
  const lyrics = track?.lyrics;
  return (
    <DialogFrame open={Boolean(track)} onOpenChange={onOpenChange} title="Track metadata" description={track ? `${track.artist || "Unknown artist"} — ${track.title}` : undefined}>
      {track && <dl className="metadata-grid">
        <div><dt>Duration</dt><dd>{formatDuration(track.duration)}</dd></div>
        <div><dt>Added</dt><dd>{formatDate(track.createdAt)}</dd></div>
        <div><dt>Audio files</dt><dd>{media.length ? media.map((file) => file.formatType.toUpperCase()).join(", ") : "None registered"}</dd></div>
        <div><dt>Lyrics</dt><dd>{lyrics?.hasOriginal || lyrics?.hasPtbr ? [lyrics.hasOriginal && "Original", lyrics.hasPtbr && "PT-BR"].filter(Boolean).join(" · ") : "Not available"}</dd></div>
        <div className="metadata-wide"><dt>Source URL</dt><dd className="metadata-url">{track.sourceUrl || "—"}</dd></div>
        {lyrics?.originalUrl && <div className="metadata-wide"><dt>Original lyrics source</dt><dd className="metadata-url"><a href={lyrics.originalUrl} target="_blank" rel="noreferrer">{lyrics.originalUrl}</a></dd></div>}
        {lyrics?.ptbrUrl && <div className="metadata-wide"><dt>PT-BR lyrics source</dt><dd className="metadata-url"><a href={lyrics.ptbrUrl} target="_blank" rel="noreferrer">{lyrics.ptbrUrl}</a></dd></div>}
        <div className="metadata-wide"><dt>Library folder</dt><dd className="metadata-url">{track.folderName || "—"}</dd></div>
      </dl>}
      <div className="dialog-footer metadata-footer"><Dialog.Close asChild><button className="button button-secondary" type="button">Done</button></Dialog.Close></div>
    </DialogFrame>
  );
}

function ConfirmDialog({ state, onOpenChange, onConfirm }: { state: ConfirmState; onOpenChange: (open: boolean) => void; onConfirm: () => void }) {
  const isTrack = state?.kind === "track";
  const title = isTrack ? state.track.title : state?.kind === "playlist" ? state.playlist.name : "";
  return (
    <DialogFrame open={Boolean(state)} onOpenChange={onOpenChange} title={isTrack ? "Delete this track?" : "Delete this playlist?"} description={isTrack ? `“${title}” and its local audio and lyric files will be removed. This cannot be undone.` : `“${title}” will be removed. Its tracks will stay in your library.`} className="confirm-dialog">
      <div className="dialog-footer confirm-footer">
        <Dialog.Close asChild><button className="button button-quiet" type="button">Cancel</button></Dialog.Close>
        <button className="button button-danger" type="button" onClick={onConfirm}><Trash2 size={15} />{isTrack ? "Delete track" : "Delete playlist"}</button>
      </div>
    </DialogFrame>
  );
}
