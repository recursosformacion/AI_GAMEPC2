import { createSsrStore } from "./createSsrStore";
import { apiClient } from "../api/ApiClient";
import type { SystemHealth } from "../api/types";

interface SystemState {
  health: SystemHealth | null;
  load: () => Promise<void>;
}

export const useSystem = createSsrStore<SystemState>((set) => ({
  health: null,
  load: async () => {
    try {
      const health = await apiClient.get<SystemHealth>("/system/health");
      set({ health });
    } catch {
      set({ health: null });
    }
  },
}));
