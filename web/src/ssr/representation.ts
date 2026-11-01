import type { RepresentationSheet } from "../api/types";

declare global {
  var __OSAP_REPRESENTATION__: { id: string; sheet: RepresentationSheet | null; status: "ok" | "missing" | "loading" } | undefined;
}

export function setSsrRepresentation(data: typeof globalThis.__OSAP_REPRESENTATION__): void {
  globalThis.__OSAP_REPRESENTATION__ = data;
}

export function ssrRepresentation(id: string) {
  const globalState = (globalThis as { __OSAP_STATE__?: { representation?: typeof globalThis.__OSAP_REPRESENTATION__ } })
    .__OSAP_STATE__;
  const value = globalThis.__OSAP_REPRESENTATION__ ?? globalState?.representation;
  return value && value.id === id ? value : undefined;
}
