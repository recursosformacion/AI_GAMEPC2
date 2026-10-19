import type { NavigateFunction } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { IntentResponse, SearchRequest } from "../api/types";
import { pushRecentSearch } from "./recentSearches";
import { useSearches } from "./searches";

// Búsquedas de repertorio anónimo/tradicional: el texto libre devuelve muy pocos
// resultados (el índice full-text no cubre los 86k de «Anónimo»); se traducen a un filtro
// por compositor, que sí los devuelve todos.
const PSEUDO_COMPOSERS: Record<string, string> = {
  anonimo: "Anónimo",
  "anónimo": "Anónimo",
  anonima: "Anónimo",
  "anónima": "Anónimo",
  anonymous: "Anónimo",
  anon: "Anónimo",
  tradicional: "Tradicional",
  traditional: "Tradicional",
  traditionell: "Tradicional",
  popular: "Tradicional",
  populares: "Tradicional",
  folk: "Tradicional",
  desconocido: "Desconocido",
  desconocida: "Desconocido",
  unknown: "Desconocido",
  varios: "Varios",
  various: "Varios",
};

function pseudoComposerLabel(query: string): string | null {
  return PSEUDO_COMPOSERS[query.trim().toLowerCase()] ?? null;
}

// Entity Resolution drives navigation: search → intent → the right entity page.
// Intent is resolved FIRST, then exactly ONE search runs (the composer path used to
// search twice, which made the results flash/reload and doubled the provider work).
export async function searchAndGo(navigate: NavigateFunction, payload: SearchRequest): Promise<void> {
  const query = payload.composer || payload.catalogue || payload.query || "";
  // Historial local para el cuadro «Búsquedas recientes» de la portada.
  pushRecentSearch(payload);
  const pseudo = pseudoComposerLabel(query);
  if (pseudo !== null) {
    await useSearches.getState().create({ query: "", composer: pseudo, limit: 30 });
    navigate("/candidates");
    return;
  }
  let intent: IntentResponse = { type: "work", label: query };
  try {
    intent = await apiClient.get<IntentResponse>(`/intent?query=${encodeURIComponent(query)}`);
  } catch {
    // fall back to "work" → Matching Works
  }
  if (intent.type === "composer") {
    // Single structured search by the extracted composer name (intent.label).
    await useSearches.getState().create({ query: "", composer: intent.label, limit: 30 });
    navigate("/composer");
  } else {
    // Los trabajos y las búsquedas por catálogo van a la MISMA página de resultados: antes el
    // catálogo se enviaba a `/resolution`, con otra presentación, y parecía una página distinta.
    // work: si la query mezclaba título+compositor, busca con ambos ("ave verum mozart").
    const req = intent.composer
      ? { ...payload, query: intent.label || payload.query, composer: intent.composer }
      : payload;
    await useSearches.getState().create(req);
    navigate("/candidates");
  }
}
