import type { NavigateFunction } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { IntentResponse, SearchRequest } from "../api/types";
import { useSearches } from "./searches";

// Entity Resolution drives navigation: search → intent → the right entity page.
// Intent is resolved FIRST, then exactly ONE search runs (the composer path used to
// search twice, which made the results flash/reload and doubled the provider work).
export async function searchAndGo(navigate: NavigateFunction, payload: SearchRequest): Promise<void> {
  const query = payload.composer || payload.catalogue || payload.query || "";
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
  } else if (intent.type === "catalogue") {
    await useSearches.getState().create(payload);
    navigate("/resolution");
  } else {
    // work: si la query mezclaba título+compositor, busca con ambos ("ave verum mozart").
    const req = intent.composer
      ? { ...payload, query: intent.label || payload.query, composer: intent.composer }
      : payload;
    await useSearches.getState().create(req);
    navigate("/candidates");
  }
}
