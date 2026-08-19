import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { SearchRequest, SearchResponse } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SearchesState extends AsyncSlice<SearchResponse> {
  selectedWorkId: string | null;
  lastRequest: SearchRequest | null;
  polling: boolean;
  create: (req: SearchRequest) => Promise<void>;
  get: (id: string) => Promise<void>;
  selectWork: (workId: string) => void;
}

const POLL_INTERVAL_MS = 1500;
const POLL_MAX_MS = 120_000;

export const useSearches = create<SearchesState>((set) => ({
  ...initialAsync,
  selectedWorkId: null,
  lastRequest: null,
  polling: false,
  create: async (req) => {
    set({ loading: true, error: null, selectedWorkId: null, lastRequest: req });
    try {
      const data = await apiClient.post<SearchResponse>("/searches", req);
      set({ data, loading: false, error: null });
      // Búsqueda asíncrona: poll hasta que termine (progreso/resultados parciales).
      if (data.status === "running" || data.status === undefined) {
        set({ polling: true });
        const started = Date.now();
        const poll = async () => {
          const current = useSearches.getState().data;
          if (!current || current.status === "done" || current.status === "error") {
            set({ polling: false });
            return;
          }
          if (Date.now() - started > POLL_MAX_MS) {
            set({ polling: false });
            return;
          }
          try {
            const fresh = await apiClient.get<SearchResponse>(`/searches/${current.search_id}`);
            set({ data: fresh, error: null });
            if (fresh.status === "running") {
              setTimeout(poll, POLL_INTERVAL_MS);
            } else {
              set({ polling: false });
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
  get: async (id) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<SearchResponse>(`/searches/${id}`);
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  selectWork: (workId) => set({ selectedWorkId: workId }),
}));
