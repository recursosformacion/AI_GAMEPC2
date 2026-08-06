import { useEffect } from "react";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import { useSystem } from "../state/system";

export function DashboardPage() {
  const health = useSystem((s) => s.health);
  const version = useSystem((s) => s.version);
  const statistics = useSystem((s) => s.statistics);
  const loadAll = useSystem((s) => s.loadAll);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const loading = health.loading || version.loading || statistics.loading;
  const error = health.error ?? version.error ?? statistics.error;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Dashboard</h1>
      <Envelope loading={loading} error={error} data={statistics.data} isEmpty={() => false}>
        {(stats) => (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Card title="Providers">{stats.providers}</Card>
              <Card title="Searches">{stats.searches}</Card>
              <Card title="Jobs">{stats.jobs}</Card>
            </div>
            <p className="text-sm text-osap-muted">Health: {health.data?.status ?? "–"} · Version: {version.data?.version ?? "–"}</p>
          </>
        )}
      </Envelope>
    </div>
  );
}
