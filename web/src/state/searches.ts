import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { SearchRequest, SearchResponse } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SearchesState extends AsyncSlice<SearchResponse> {
  selectedWorkId: string | null;
  lastRequest: SearchRequest | null;
  create: (req: SearchRequest) => Promise<void>;
  get: (id: string) => Promise<void>;
  selectWork: (workId: string) => void;
}

export const useSearches = create<SearchesState>((set) => ({
  ...initialAsync,
  selectedWorkId: null,
  lastRequest: null,
  create: async (req) => {
    set({ loading: true, error: null, selectedWorkId: null, lastRequest: req });
    try {
      const data = await apiClient.post<SearchResponse>("/searches", req);
      set({ data, loading: false, error: null });
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
