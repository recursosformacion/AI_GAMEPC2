// SupportApiClient: llama a osap-support (HTTP API real) a través del proxy de Apache.
//
// Base URL: bajo el mismo origen que osap-app, Apache proxya /support-api/ → osap-support
// (8300). Puede sobreescribirse con VITE_SUPPORT_API (p. ej. dominio propio) para
// despliegues donde support NO comparte origen; entonces osap-support debe permitir en
// CORS SOLO este origen.
//
// Nunca declara éxito que el backend no confirmó. Errores de red/HTTP se propagan para
// que la UI los muestre (nada de "solicitud realizada" ficticia).

import { ApiError } from "../api/errors";
import type { CheckoutResult, MembershipView } from "./supportGateway";

const SUPPORT_BASE =
  (globalThis as { VITE_SUPPORT_API?: string }).VITE_SUPPORT_API?.replace(/\/$/, "") ??
  "/support-api/api/v1";

import { useAuth } from "../state/auth";

export class SupportApiClient {
  constructor(
    private readonly baseUrl: string = SUPPORT_BASE,
    private readonly fetcher?: typeof fetch,
  ) {}

  private async doFetch(input: string, init?: RequestInit): Promise<Response> {
    const fetchImpl =
      this.fetcher ?? (typeof globalThis !== "undefined" ? globalThis.fetch : undefined);
    if (!fetchImpl) {
      throw new ApiError("NO_FETCH", "fetch no disponible", { status: 503 });
    }
    return fetchImpl(input, init);
  }

  async getMyMembership(accessToken: string): Promise<MembershipView> {
    return (await this.get("/membership/me", accessToken)) as MembershipView;
  }

  async startDonation(
    accessToken: string,
    body: { amount_minor: number; currency: string; return_url: string },
  ): Promise<CheckoutResult> {
    return (await this.post("/checkouts/donation", accessToken, body)) as CheckoutResult;
  }

  async startMembership(
    accessToken: string,
    body: { level: string; periodicity: string; return_url: string },
  ): Promise<CheckoutResult> {
    return (await this.post("/checkouts/membership", accessToken, body)) as CheckoutResult;
  }

  private async get(path: string, token: string): Promise<unknown> {
    return this.decode(
      await this._authorizedFetch(`${this.baseUrl}${path}`, {
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      }, token),
    );
  }

  private async post(path: string, token: string, body: unknown): Promise<unknown> {
    return this.decode(
      await this._authorizedFetch(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(body),
      }, token),
    );
  }

  // 401 → refresh (una vez) → reintento. Si vuelve a fallar, sesión expirada: logout.
  private async _authorizedFetch(
    input: string,
    init: RequestInit,
    _token: string,
  ): Promise<Response> {
    let res = await this.doFetch(input, init);
    if (res.status !== 401) {
      return res;
    }
    const { refreshSession } = useAuth.getState();
    const refreshed = await refreshSession();
    if (!refreshed) {
      return res; // refreshSession ya hizo logout
    }
    const newToken = useAuth.getState().accessToken ?? "";
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${newToken}`);
    res = await this.doFetch(input, { ...init, headers });
    if (res.status === 401) {
      useAuth.getState().logout();
    }
    return res;
  }

  private async decode(res: Response): Promise<unknown> {
    if (res.status === 401) {
      throw new ApiError("UNAUTHORIZED", "autenticación requerida", { status: 401 });
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* sin body JSON */
      }
      throw new ApiError("SUPPORT_ERROR", detail, { status: res.status });
    }
    return res.json();
  }
}

export const supportApiClient = new SupportApiClient();
