import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { JobResponse } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface JobsState extends AsyncSlice<JobResponse[]> {
  list: () => Promise<void>;
  create: (type: string) => Promise<void>;
}

export const useJobs = create<JobsState>((set) => ({
  ...initialAsync,
  list: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<JobResponse[]>("/jobs");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  create: async (type) => {
    set({ loading: true, error: null });
    try {
      await apiClient.post<JobResponse>("/jobs", { type });
      const data = await apiClient.get<JobResponse[]>("/jobs");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
