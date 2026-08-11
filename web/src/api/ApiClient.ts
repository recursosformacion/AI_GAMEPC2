// ApiClient: the ONLY HTTP access point of the web client.
//
// Responsibilities:
//  - calls /api/v1/... endpoints
//  - serializes/deserializes DTOs
//  - interprets the uniform envelope (success / request_id / data / error)
//  - transforms REST errors into ApiError (code/message/details)
//
// Pages never call fetch/axios directly. Everything goes through this class.

import type {
  ComposerDetail,
  ComposerList,
  ComposerStatistics,
  ComposerSummary,
  ComposerWorks,
  Envelope,
  MergeComposersResult,
  SourcePreview,
  SourceSuggestion,
  RegisterResult,
  VerifyEmailResult,
  VotesOverview,
  WorkDetail,
  WorkStatistics,
} from "./types";
import { ApiError } from "./errors";

export const API_PREFIX = "/api/v1";

export interface AuthHandler {
  getToken: () => string | null;
  refresh: () => Promise<boolean>;
  logout: () => void;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch | undefined;
  private token: string | null = null;
  private auth: AuthHandler = {
    getToken: () => null,
    refresh: async () => false,
    logout: () => undefined,
  };

  constructor(baseUrl: string = API_PREFIX, fetcher?: typeof fetch) {
    this.baseUrl = baseUrl;
    // If no fetcher is provided, `globalThis.fetch` is resolved at call time. This keeps
    // the client testable (tests can stub `globalThis.fetch`) and works in the browser.
    this.fetcher = fetcher;
  }

  setToken(token: string | null): void {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
  }

  setAuthHandler(auth: AuthHandler): void {
    this.auth = auth;
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  async getComposers(q: string, limit: number, offset: number, review?: string): Promise<ComposerList> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q) {
      params.set("q", q);
    }
    if (review) {
      params.set("review", review);
    }
    return this.get<ComposerList>(`/composers?${params.toString()}`);
  }

  async getComposer(composerId: string): Promise<ComposerDetail> {
    return this.get<ComposerDetail>(`/composers/${encodeURIComponent(composerId)}`);
  }

  async getWork(workId: string): Promise<WorkDetail> {
    return this.get<WorkDetail>(`/works/${encodeURIComponent(workId)}`);
  }

  async getComposerWorks(composerId: string, limit: number, offset: number): Promise<ComposerWorks> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.get<ComposerWorks>(`/composers/${encodeURIComponent(composerId)}/works?${params.toString()}`);
  }

  async mergeComposers(targetId: string, sources: string[]): Promise<MergeComposersResult> {
    return this.post<MergeComposersResult>("/admin/composers/merge", { target_id: targetId, sources });
  }

  async createComposer(name: string): Promise<ComposerSummary> {
    return this.post<ComposerSummary>("/admin/composers", { name });
  }

  async reviewComposer(composerId: string, reviewStatus: string): Promise<ComposerDetail> {
    return this.post<ComposerDetail>(`/admin/composers/${encodeURIComponent(composerId)}/review`, {
      review_status: reviewStatus,
    });
  }

  async previewSource(url: string): Promise<SourcePreview> {
    return this.post<SourcePreview>("/sources/preview", { url });
  }

  async suggestSource(payload: {
    name: string;
    type: string;
    location: string;
    mapping: Record<string, unknown>;
  }): Promise<SourceSuggestion> {
    return this.post<SourceSuggestion>("/sources/suggest", payload);
  }

  async listSourceSuggestions(): Promise<SourceSuggestion[]> {
    return this.get<SourceSuggestion[]>("/admin/source-suggestions");
  }

  async resolveSourceSuggestion(suggestionId: string, action: string, message: string): Promise<SourceSuggestion> {
    return this.post<SourceSuggestion>(`/admin/source-suggestions/${encodeURIComponent(suggestionId)}/resolve`, {
      action,
      message,
    });
  }

  async getWorkStatistics(workId: string): Promise<WorkStatistics> {
    return this.get<WorkStatistics>(`/works/${encodeURIComponent(workId)}/statistics`);
  }

  async getComposerStatistics(composerId: string): Promise<ComposerStatistics> {
    return this.get<ComposerStatistics>(`/composers/${encodeURIComponent(composerId)}/statistics`);
  }

  async getVotesOverview(): Promise<VotesOverview> {
    return this.get<VotesOverview>("/admin/votes");
  }

  async register(email: string, password: string, name?: string): Promise<RegisterResult> {
    return this.post<RegisterResult>("/auth/register", { email, password, name });
  }

  async verifyEmail(token: string): Promise<VerifyEmailResult> {
    return this.post<VerifyEmailResult>("/auth/verify-email", { token });
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    let retried = false;
    // eslint-disable-next-line no-constant-condition
    for (;;) {
      const headers: Record<string, string> = {};
      if (body !== undefined) {
        headers["Content-Type"] = "application/json";
      }
      const token = this.auth.getToken() ?? this.token;
      if (token !== null) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      let response: Response;
      try {
        // `fetch` must be invoked with `this` bound to globalThis/window, otherwise it
        // throws "Illegal invocation". Pages never touch this detail.
        response = await fetchImpl.call(globalThis, `${this.baseUrl}${path}`, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
        });
      } catch (cause) {
        throw new ApiError("NETWORK", "Network error", { cause: String(cause) });
      }

      // 401 → refresh (una vez) → retry único. Si vuelve a 401 → logout.
      if (response.status === 401 && !retried) {
        retried = true;
        const refreshed = await this.auth.refresh();
        if (refreshed) {
          continue;
        }
        throw new ApiError("UNAUTHORIZED", "Session expired");
      }
      if (response.status === 401 && retried) {
        this.auth.logout();
      }

      let parsed: Envelope<T> | null = null;
      try {
        parsed = (await response.json()) as Envelope<T>;
      } catch {
        parsed = null;
      }

      if (parsed === null || typeof parsed !== "object") {
        throw new ApiError("INVALID_RESPONSE", `Invalid response (HTTP ${response.status})`);
      }

      if (parsed.success === true) {
        return parsed.data;
      }

      if ("error" in parsed && parsed.error !== undefined && parsed.error !== null) {
        throw new ApiError(parsed.error.code, parsed.error.message, parsed.error.details);
      }

      throw new ApiError("INVALID_RESPONSE", `Unexpected response (HTTP ${response.status})`);
    }
  }
}

export const apiClient = new ApiClient();
