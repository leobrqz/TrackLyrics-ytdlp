import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { BackendError, type BackendEvent } from "./types";

let requestCounter = 0;

function nextRequestId(): string {
  requestCounter += 1;
  return globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${requestCounter}`;
}

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function backendRequest<T>(command: string, payload: Record<string, unknown> = {}): Promise<T> {
  if (!isTauriRuntime()) {
    throw new BackendError(
      "desktop-runtime-required",
      "A biblioteca local fica disponível no aplicativo TrackLyrics.",
    );
  }

  const id = nextRequestId();
  try {
    return await invoke<T>("backend_request", { id, command, payload });
  } catch (error) {
    const message = typeof error === "string" ? error : error instanceof Error ? error.message : "The action could not be completed.";
    const separator = message.indexOf(": ");
    if (separator > 0 && /^[A-Z_]+$/.test(message.slice(0, separator))) {
      throw new BackendError(message.slice(0, separator).toLowerCase(), message.slice(separator + 2));
    }
    throw new BackendError("backend-error", message);
  }
}

export async function listenBackendEvents(handler: (event: BackendEvent) => void): Promise<UnlistenFn> {
  if (!isTauriRuntime()) return () => undefined;
  return listen<BackendEvent>("backend_event", (event) => handler(event.payload));
}
