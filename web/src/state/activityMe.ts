import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { ActivityMe } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface ActivityMeState extends AsyncSlice<ActivityMe> {
  load: (from?: string, to?: string) => Promise<void>;
}

export const useActivityMe = create<ActivityMeState>((set) => ({
  ...initialAsync,
  load: async (from, to) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.getActivityMe(from, to);
      set({ data, loading: false, error: null });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof ApiError ? err : new ApiError("UNKNOWN", "Unexpected error"),
      });
    }
  },
}));
