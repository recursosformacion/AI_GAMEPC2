// Estado de sesiones de resolución/adquisición de obras.
// "Resolver obra" crea una ResolutionSession (POST /works/resolve, no bloqueante) y
// consulta su estado con polling hasta que termina (acquiring → complete|partial|expired).

import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { ResolutionSession } from "../api/types";

const POLL_INTERVAL_MS = 1500;
const POLL_MAX_MS = 120_000;
const TERMINAL = new Set(["complete", "partial", "expired", "failed"]);

interface ResolutionState {
  session: ResolutionSession | null;
  loading: boolean;
  polling: boolean;
  error: ApiError | null;
  resolve: (query: string) => Promise<void>;
  refresh: (sessionId: string) => Promise<void>;
  clear: () => void;
}

export const useResolution = create<ResolutionState>((set) => ({
  session: null,
  loading: false,
  polling: false,
  error: null,
  resolve: async (query) => {
    set({ loading: true, error: null, session: null });
    try {
      const session = await apiClient.createResolutionSession({ query });
      set({ session, loading: false, error: null });
      if (!TERMINAL.has(session.status)) {
        set({ polling: true });
        const started = Date.now();
        const poll = async () => {
          const current = useResolution.getState().session;
          if (!current) {
            set({ polling: false });
            return;
          }
          if (TERMINAL.has(current.status) || Date.now() - started > POLL_MAX_MS) {
            set({ polling: false });
            return;
          }
          try {
            const fresh = await apiClient.getResolutionSession(current.session_id);
            set({ session: fresh, error: null });
            if (TERMINAL.has(fresh.status) || Date.now() - started > POLL_MAX_MS) {
              set({ polling: false });
            } else {
              setTimeout(poll, POLL_INTERVAL_MS);
            }
          } catch (e) {
            set({ polling: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
          }
        };
        setTimeout(poll, POLL_INTERVAL_MS);
      }
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  refresh: async (sessionId) => {
    try {
      const session = await apiClient.getResolutionSession(sessionId);
      set({ session, error: null });
    } catch (e) {
      set({ error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  clear: () => set({ session: null, loading: false, polling: false, error: null }),
}));
