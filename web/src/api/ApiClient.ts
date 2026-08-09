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
  ComposerWorks,
  Envelope,
  MergeComposersResult,
} from "./types";
import { ApiError } from "./errors";

export const API_PREFIX = "/api/v1";

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch | undefined;
  private token: string | null = null;

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

  async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  async getComposers(q: string, limit: number, offset: number): Promise<ComposerList> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q) {
      params.set("q", q);
    }
    return this.get<ComposerList>(`/composers?${params.toString()}`);
  }

  async getComposer(composerId: string): Promise<ComposerDetail> {
    return this.get<ComposerDetail>(`/composers/${encodeURIComponent(composerId)}`);
  }

  async getComposerWorks(composerId: string, limit: number, offset: number): Promise<ComposerWorks> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.get<ComposerWorks>(`/composers/${encodeURIComponent(composerId)}/works?${params.toString()}`);
  }

  async mergeComposers(targetId: string, sourceIds: string[]): Promise<MergeComposersResult> {
    return this.post<MergeComposersResult>(
      `/admin/composers/${encodeURIComponent(targetId)}/merge`,
      { source_ids: sourceIds },
    );
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    const headers: Record<string, string> = {};
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (this.token !== null) {
      headers["Authorization"] = `Bearer ${this.token}`;
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

export const apiClient = new ApiClient();
