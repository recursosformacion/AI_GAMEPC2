import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { ProviderResponse } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface ProvidersState extends AsyncSlice<ProviderResponse[]> {
  list: () => Promise<void>;
}

export const useProviders = create<ProvidersState>((set) => ({
  ...initialAsync,
  list: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<ProviderResponse[]>("/providers");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
