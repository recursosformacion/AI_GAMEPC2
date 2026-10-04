import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { Epoch } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface EpochsState extends AsyncSlice<Epoch[]> {
  list: () => Promise<void>;
}

// Épocas históricas (catálogo público). El orden lo fija el backend (por año).
export const useEpochs = create<EpochsState>((set) => ({
  ...initialAsync,
  list: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.getEpochs();
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
