import { ApiError } from "../api/errors";

// Minimal, centralized async state per resource. Reflects exactly what the API returns.
export interface AsyncSlice<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

export const initialAsync = { data: null, loading: false, error: null };
