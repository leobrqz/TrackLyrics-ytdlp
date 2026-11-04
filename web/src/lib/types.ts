export type Theme = "dark" | "light";
export type QueueMode = "fifo" | "parallel";
export type LibraryView = "all" | "favorites" | "downloads" | `playlist:${number}`;
export type DownloadStatus = "pending" | "running" | "done" | "failed" | string;

export interface MediaFile {
  id: number;
  trackId: number;
  fileName: string;
  formatType: string;
  hasAudio: boolean;
}

export interface Lyrics {
  trackId: number;
  originalPath: string | null;
  ptbrPath: string | null;
  originalUrl: string | null;
  ptbrUrl: string | null;
  hasOriginal: boolean;
  hasPtbr: boolean;
  searchStatus?: "unknown" | "pending" | "complete" | "failed" | string;
  originalText?: string | null;
  ptbrText?: string | null;
}

export interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
  favorite: boolean;
  folderName: string;
  sourceUrl: string;
  createdAt: string;
  mediaFiles: MediaFile[];
  lyrics: Lyrics | null;
}

export interface Playlist {
  id: number;
  name: string;
  createdAt: string;
  trackCount?: number;
}

export interface DownloadJob {
  jobId: string;
  url: string;
  formatType: "mp3" | "wav" | string;
  status: DownloadStatus;
  error: string | null;
  stage?: string;
  progress?: number;
  title?: string | null;
  artist?: string | null;
}

export interface AppSettings {
  theme: Theme;
  downloadQueueMode: QueueMode;
  downloadParallelWorkers: number;
  lyricsParallelWithDownload: boolean;
  volume: number;
}

export interface BootstrapData {
  tracks: Track[];
  playlists: Playlist[];
  settings: Partial<AppSettings>;
  queue: DownloadJob[];
}

export interface EnqueueResult {
  jobs: DownloadJob[];
  failedInputs: Array<{ url: string; message: string }>;
}

export type BackendEventName =
  | "downloads.progress"
  | "downloads.status"
  | "library.track_saved"
  | "lyrics.ready"
  | "downloads.duplicate"
  | "app.error";

export interface BackendEvent<T = Record<string, unknown>> {
  event: BackendEventName;
  data: T;
}

export interface BackendErrorShape {
  code: string;
  message: string;
}

export class BackendError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "BackendError";
    this.code = code;
  }
}

export const DEFAULT_SETTINGS: AppSettings = {
  theme: "dark",
  downloadQueueMode: "fifo",
  downloadParallelWorkers: 3,
  lyricsParallelWithDownload: false,
  volume: 0.8,
};

export function normalizeSettings(input: Partial<AppSettings> | Record<string, unknown> = {}): AppSettings {
  const rawVolume = Number(input.volume ?? DEFAULT_SETTINGS.volume);
  const volume = Number.isFinite(rawVolume)
    ? Math.max(0, Math.min(1, rawVolume > 1 ? rawVolume / 100 : rawVolume))
    : DEFAULT_SETTINGS.volume;
  const workers = Number(input.downloadParallelWorkers ?? DEFAULT_SETTINGS.downloadParallelWorkers);

  return {
    theme: input.theme === "light" ? "light" : "dark",
    downloadQueueMode: input.downloadQueueMode === "parallel" ? "parallel" : "fifo",
    downloadParallelWorkers: Number.isFinite(workers) ? Math.max(2, Math.min(8, Math.round(workers))) : 3,
    lyricsParallelWithDownload: Boolean(input.lyricsParallelWithDownload),
    volume,
  };
}

export function normalizeTrack(track: Partial<Track> & Pick<Track, "id" | "title" | "artist">): Track {
  return {
    id: track.id,
    title: track.title,
    artist: track.artist,
    duration: Number(track.duration ?? 0),
    favorite: Boolean(track.favorite),
    folderName: track.folderName ?? "",
    sourceUrl: track.sourceUrl ?? "",
    createdAt: track.createdAt ?? "",
    mediaFiles: Array.isArray(track.mediaFiles) ? track.mediaFiles : [],
    lyrics: track.lyrics ?? null,
  };
}
