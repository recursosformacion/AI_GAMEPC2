import { useEffect } from "react";
import { Envelope } from "../components/Envelope";
import { ResultList } from "../components/ResultList";
import { useProviders } from "../state/providers";

export function ProvidersPage() {
  const { data, loading, error, list } = useProviders();
  useEffect(() => {
    void list();
  }, [list]);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Administration — Providers</h1>
      <Envelope loading={loading} error={error} data={data} emptyMessage="No providers">
        {(providers) => (
          <ResultList
            items={providers}
            keyOf={(p) => p.provider_id}
            renderItem={(p) => (
              <span>
                {p.name} ({p.provider_id}) — {p.available ? "available" : "unavailable"} — {p.formats.join(", ")}
              </span>
            )}
          />
        )}
      </Envelope>
    </div>
  );
}
