import type { NavigateFunction } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { IntentResponse, SearchRequest } from "../api/types";
import { useSearches } from "./searches";

// Entity Resolution drives navigation: search → intent → the right entity page.
export async function searchAndGo(navigate: NavigateFunction, payload: SearchRequest): Promise<void> {
  await useSearches.getState().create(payload);
  const query = payload.composer || payload.catalogue || payload.query || "";  let intent: IntentResponse = { type: "work", label: query };
  try {
    intent = await apiClient.get<IntentResponse>(`/intent?query=${encodeURIComponent(query)}`);
  } catch {
    // fall back to "work" → Matching Works
  }
  if (intent.type === "composer") {
    // Re-search structured by composer so only that composer's works appear (no stray works).
    await useSearches.getState().create({ query: "", composer: query, limit: 50 });
    navigate("/composer");
  } else if (intent.type === "catalogue") {
    navigate("/resolution");
  } else {
    navigate("/candidates");
  }
}
