import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { WorkStatistics } from "../api/types";
import { RatingView } from "./RatingView";

// Valoración agregada de una obra (proxy de osap-storage).
// La agregación es nocturna: tras votar no cambia de inmediato; el Web re-consulta.
export function WorkRating({ workId }: { workId: string }) {
  const [stats, setStats] = useState<WorkStatistics | null>(null);

  useEffect(() => {
    let active = true;
    apiClient
      .getWorkStatistics(workId)
      .then((s) => active && setStats(s))
      .catch(() => active && setStats(null));
    return () => {
      active = false;
    };
  }, [workId]);

  if (stats === null) {
    return null;
  }
  return (
    <div className="flex items-center gap-2">
      <RatingView rating={stats.rating} voteCount={stats.vote_count} />
    </div>
  );
}
