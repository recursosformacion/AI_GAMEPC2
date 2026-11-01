import type { SsrState } from "./types";

type ClassificationState = NonNullable<SsrState["classification"]>;

declare global {
  var __OSAP_CLASSIFICATION__: ClassificationState | undefined;
}

export function setSsrClassification(data: ClassificationState | undefined): void {
  globalThis.__OSAP_CLASSIFICATION__ = data;
}

/** Datos precargados por el SSR para pintar la primera respuesta sin esperar al cliente. */
export function ssrClassification<K extends keyof ClassificationState>(
  key: K,
): ClassificationState[K] | undefined {
  return globalThis.__OSAP_CLASSIFICATION__?.[key];
}
