import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";
import { ComposerPage } from "./ComposerPage";

// Detalle público de un compositor: muestra la MISMA pantalla que buscar con ese
// compositor (pipeline completo, colecciones, acordeón de obras y representaciones).
export function ComposerDetailPage() {
  const { composerId = "" } = useParams<{ composerId: string }>();
  const detail = useComposers((s) => s.detail);
  const fetchDetail = useComposers((s) => s.fetchDetail);

  useEffect(() => {
    void fetchDetail(composerId);
  }, [fetchDetail, composerId]);

  // Igual que una búsqueda con ese compositor.
  useEffect(() => {
    if (detail?.name) {
      void useSearches.getState().create({ query: "", composer: detail.name, limit: 50 });
    }
  }, [detail?.name]);

  return <ComposerPage />;
}
