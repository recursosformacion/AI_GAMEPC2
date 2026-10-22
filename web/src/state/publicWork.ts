import { createSsrStore } from "./createSsrStore";
import { apiClient } from "../api/ApiClient";
import type { PublicWork } from "../api/types";

type PublicWorkStatus = "idle" | "loading" | "ok" | "missing";

interface PublicWorkState {
  sheet: PublicWork | null;
  status: PublicWorkStatus;
  loadedId: string | null;
  load: (workId: string) => Promise<void>;
}

/** Ficha pública de obra (la usan la página /obras y el SSR). */
export const usePublicWork = createSsrStore<PublicWorkState>((set) => ({
  sheet: null,
  status: "idle",
  loadedId: null,
  load: async (workId) => {
    set({ status: "loading" });
    try {
      const sheet = await apiClient.getPublicWork(workId);
      set({ sheet, status: "ok", loadedId: workId });
    } catch {
      set({ sheet: null, status: "missing", loadedId: workId });
    }
  },
}));
