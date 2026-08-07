import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { RepositorySource, RepositorySourceSummary } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SourcesState {
  list: AsyncSlice<RepositorySourceSummary[]>;
  detail: AsyncSlice<RepositorySource | null>;
  loadList: () => Promise<void>;
  loadDetail: (sourceId: string) => Promise<void>;
}

const clear = () => ({ data: null, loading: false, error: null });

export const useSources = create<SourcesState>((set) => ({
  list: initialAsync,
  detail: initialAsync,
  loadList: async () => {
    set({ list: { data: null, loading: true, error: null } });
    try {
      const data = await apiClient.get<RepositorySourceSummary[]>("/repository-sources");
      set({ list: { data, loading: false, error: null } });
    } catch (e) {
      set({ list: { ...clear(), error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) } });
    }
  },
  loadDetail: async (sourceId) => {
    set({ detail: { data: null, loading: true, error: null } });
    try {
      const data = await apiClient.get<RepositorySource>(`/repository-sources/${sourceId}`);
      set({ detail: { data, loading: false, error: null } });
    } catch (e) {
      set({ detail: { ...clear(), error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) } });
    }
  },
}));
