import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { SystemHealth, SystemStatistics, SystemVersion } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface SystemState {
  health: AsyncSlice<SystemHealth>;
  version: AsyncSlice<SystemVersion>;
  statistics: AsyncSlice<SystemStatistics>;
  loadAll: () => Promise<void>;
}

const clear = () => ({ data: null, loading: false, error: null });

export const useSystem = create<SystemState>((set) => ({
  health: initialAsync,
  version: initialAsync,
  statistics: initialAsync,
  loadAll: async () => {
    set({ health: { ...clear(), loading: true } });
    try {
      const health = await apiClient.get<SystemHealth>("/system/health");
      const version = await apiClient.get<SystemVersion>("/system/version");
      const statistics = await apiClient.get<SystemStatistics>("/system/statistics");
      set({
        health: { data: health, loading: false, error: null },
        version: { data: version, loading: false, error: null },
        statistics: { data: statistics, loading: false, error: null },
      });
    } catch (e) {
      const error = e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e));
      set((s) => ({
        health: { ...s.health, loading: false, error },
        version: { ...s.version, loading: false, error },
        statistics: { ...s.statistics, loading: false, error },
      }));
    }
  },
}));
