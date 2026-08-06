import { useState } from "react";
import { Button } from "../components/Button";
import { Envelope } from "../components/Envelope";
import { EvidenceView } from "../components/EvidenceView";
import { ResultList } from "../components/ResultList";
import { useSearches } from "../state/searches";

export function SearchesPage() {
  const { data, loading, error, create } = useSearches();
  const [query, setQuery] = useState("Ave Verum");
  const [limit, setLimit] = useState(10);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void create({ query, limit });
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Searches</h1>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-sm">
          Query
          <input
            aria-label="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="mt-1 rounded border border-osap-border px-2 py-1"
          />
        </label>
        <label className="flex flex-col text-sm">
          Limit
          <input
            aria-label="limit"
            type="number"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="mt-1 w-20 rounded border border-osap-border px-2 py-1"
          />
        </label>
        <Button type="submit">Search</Button>
      </form>
      <Envelope loading={loading} error={error} data={data} emptyMessage="No results">
        {(search) => (
          <ResultList
            items={search.results}
            keyOf={(r) => r.work.work_id}
            renderItem={(r) => (
              <div className="flex flex-col gap-1">
                <span className="font-medium">
                  {r.work.title} — {r.representation.provider} ({r.representation.format})
                </span>
                <span className="text-sm text-osap-muted">score {r.score}</span>
                <EvidenceView items={r.evidence} />
              </div>
            )}
          />
        )}
      </Envelope>
    </div>
  );
}
