import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { DiscoverSource, SessionSource, SessionSourceCreate } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SourcesState {
  list: AsyncSlice<SessionSource[]>;
  discover: AsyncSlice<DiscoverSource[]>;
  create: (req: SessionSourceCreate) => Promise<void>;
  listAll: () => Promise<void>;
  analyze: (sourceId: string) => Promise<void>;
  use: (sourceId: string) => Promise<void>;
  forget: (sourceId: string) => Promise<void>;
  loadDiscover: () => Promise<void>;
}

const clear = () => ({ data: null, loading: false, error: null });

export const useSessionSources = create<SourcesState>((set) => ({
  list: initialAsync,
  discover: initialAsync,
  create: async (req) => {
    try {
      await apiClient.post<SessionSource>("/sources", req);
      const data = await apiClient.get<SessionSource[]>("/sources");
      set({ list: { data, loading: false, error: null } });
    } catch (e) {
      set({ list: { ...clear(), error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) } });
    }
  },
  listAll: async () => {
    set({ list: { data: null, loading: true, error: null } });
    try {
      const data = await apiClient.get<SessionSource[]>("/sources");
      set({ list: { data, loading: false, error: null } });
    } catch (e) {
      set({ list: { ...clear(), error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) } });
    }
  },
  analyze: async (sourceId) => {
    await apiClient.post<SessionSource>(`/sources/${sourceId}/analyze`);
    const data = await apiClient.get<SessionSource[]>("/sources");
    set({ list: { data, loading: false, error: null } });
  },
  use: async (sourceId) => {
    await apiClient.post<SessionSource>(`/sources/${sourceId}/use`);
    const data = await apiClient.get<SessionSource[]>("/sources");
    set({ list: { data, loading: false, error: null } });
  },
  forget: async (sourceId) => {
    await apiClient.delete<unknown>(`/sources/${sourceId}`);
    const data = await apiClient.get<SessionSource[]>("/sources");
    set({ list: { data, loading: false, error: null } });
  },
  loadDiscover: async () => {
    set({ discover: { data: null, loading: true, error: null } });
    try {
      const data = await apiClient.get<DiscoverSource[]>("/discover/sources");
      set({ discover: { data, loading: false, error: null } });
    } catch (e) {
      set({ discover: { ...clear(), error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) } });
    }
  },
}));
