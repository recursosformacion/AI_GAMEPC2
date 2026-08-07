import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useSources } from "../state/repositorySources";
import { useSessionSources } from "../state/sources";

export function DiscoverPage() {
  const { t } = useI18n();
  const { list, loadList } = useSources();
  const { discover, loadDiscover } = useSessionSources();

  useEffect(() => {
    void loadList();
    void loadDiscover();
  }, [loadList, loadDiscover]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("nav.discover")}</h1>
        <Link
          to="/sources"
          className="rounded bg-osap-accent px-3 py-1.5 text-sm text-white hover:bg-osap-accent/90"
        >
          + Add a source
        </Link>
      </div>

      {/* Discover sources (suggestions) */}
      <Card title="Discover Sources">
        <Envelope loading={discover.loading} error={discover.error} data={discover.data} emptyMessage="No suggestions">
          {(sources) => (
            <ul className="grid gap-3 sm:grid-cols-2">
              {sources.map((s) => (
                <li key={s.source_id} className="rounded border border-osap-border p-3">
                  <div className="font-medium text-osap-accent">{s.name}</div>
                  <div className="text-xs text-osap-muted">
                    {s.type} · {s.origin} · {s.trust}
                  </div>
                  <div className="text-sm">{"★".repeat(Math.max(1, Math.min(5, Math.round(s.quality / 20))))} {s.quality}/100</div>
                </li>
              ))}
            </ul>
          )}
        </Envelope>
      </Card>

      {/* Collections (repository catalog) */}
      <Card title="Collections">
        <Envelope loading={list.loading} error={list.error} data={list.data} emptyMessage="No collections">
          {(sources) => (
            <ul className="grid gap-3 sm:grid-cols-2">
              {sources.map((s) => (
                <li key={s.source_id}>
                  <Link to="/catalog" className="block rounded border border-osap-border p-3 hover:border-osap-accent">
                    <span className="font-medium">{s.name}</span>
                    <span className="ml-2 text-xs text-osap-muted">
                      {s.type} · {s.origin}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Envelope>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card title="Trending works">
          <EmptyState />
        </Card>
        <Card title="Recently added">
          <EmptyState />
        </Card>
        <Card title="Most downloaded">
          <EmptyState />
        </Card>
        <Card title="Popular composers">
          <EmptyState />
        </Card>
      </div>
    </div>
  );
}
