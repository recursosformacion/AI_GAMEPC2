import type { SearchRequest } from "../api/types";

// Historial de búsquedas del navegador (local, sin servidor): alimenta el cuadro
// «Búsquedas recientes» de la portada. Se guardan las últimas 5, sin duplicados.
const KEY = "osap.recentSearches";
const MAX = 5;

export interface RecentSearch {
  /** Texto legible que se muestra en la portada. */
  label: string;
  /** Petición original, para poder repetir la búsqueda tal cual. */
  request: SearchRequest;
  /** Marca de tiempo (ms) para ordenar y como clave estable. */
  at: number;
}

/** Etiqueta legible de una búsqueda: el término o los campos estructurados usados. */
export function searchLabel(req: SearchRequest): string {
  const parts = [
    req.query?.trim(),
    req.title?.trim(),
    req.composer?.trim(),
    req.catalogue?.trim(),
  ].filter((p): p is string => Boolean(p && p.length > 0));
  if (parts.length === 0) return "";
  return [...new Set(parts)].join(" · ");
}

function isRecentSearch(value: unknown): value is RecentSearch {
  if (typeof value !== "object" || value === null) return false;
  const row = value as Record<string, unknown>;
  return typeof row.label === "string" && typeof row.at === "number" && typeof row.request === "object";
}

export function loadRecentSearches(): RecentSearch[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRecentSearch).slice(0, MAX);
  } catch {
    return [];
  }
}

/** Guarda una búsqueda al frente; ignora etiquetas vacías y duplicados. */
export function pushRecentSearch(req: SearchRequest): void {
  const label = searchLabel(req);
  if (label === "") return;
  const current = loadRecentSearches().filter(
    (row) => row.label.toLowerCase() !== label.toLowerCase(),
  );
  const next: RecentSearch[] = [{ label, request: req, at: Date.now() }, ...current].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* almacenamiento no disponible: la portada simplemente no mostrará historial */
  }
}
