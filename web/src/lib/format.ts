export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}:${String(minutes % 60).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(date);
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1000) return `${bytes} B`;
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} kB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

export function shortUrl(value: string): string {
  try {
    const url = new URL(value);
    const path = url.pathname.length > 44 ? `${url.pathname.slice(0, 41)}…` : url.pathname;
    return `${url.hostname.replace(/^www\./, "")}${path}`;
  } catch {
    return value.length > 64 ? `${value.slice(0, 61)}…` : value;
  }
}
