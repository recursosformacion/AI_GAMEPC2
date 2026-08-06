import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { SearchRequest, SearchResponse } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SearchesState extends AsyncSlice<SearchResponse> {
  create: (req: SearchRequest) => Promise<void>;
  get: (id: string) => Promise<void>;
}

export const useSearches = create<SearchesState>((set) => ({
  ...initialAsync,
  create: async (req) => {
    set({ loading: true, error: null });
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
}));
