// ApiClient: the ONLY HTTP access point of the web client.
//
// Responsibilities:
//  - calls /api/v1/... endpoints
//  - serializes/deserializes DTOs
//  - interprets the uniform envelope (success / request_id / data / error)
//  - transforms REST errors into ApiError (code/message/details)
//
// Pages never call fetch/axios directly. Everything goes through this class.

import type { Envelope } from "./types";
import { ApiError } from "./errors";

export const API_PREFIX = "/api/v1";

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(baseUrl: string = API_PREFIX, fetcher: typeof fetch = fetch) {
    this.baseUrl = baseUrl;
    // `fetch` must be invoked with `this` bound to globalThis/window, otherwise it
    // throws "Illegal invocation". Binding here keeps pages free of fetch details.
    this.fetcher = fetcher.bind(globalThis);
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
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
