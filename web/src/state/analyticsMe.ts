import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { AnalyticsMe } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface AnalyticsMeState extends AsyncSlice<AnalyticsMe> {
  load: (from?: string, to?: string) => Promise<void>;
}

export const useAnalyticsMe = create<AnalyticsMeState>((set) => ({
  ...initialAsync,
  load: async (from, to) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.getAnalyticsMe(from, to);
      set({ data, loading: false, error: null });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof ApiError ? err : new ApiError("UNKNOWN", "Unexpected error"),
      });
    }
  },
}));
