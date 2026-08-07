import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { SearchModel } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SearchModelState extends AsyncSlice<SearchModel> {
  load: () => Promise<void>;
}

export const useSearchModel = create<SearchModelState>((set) => ({
  ...initialAsync,
  load: async () => {
    set({ data: null, loading: true, error: null });
    try {
      const data = await apiClient.get<SearchModel>("/search-model");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
