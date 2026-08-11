import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useSources } from "../state/repositorySources";

export function DiscoverPage() {
  const { t } = useI18n();
  const { list, loadList } = useSources();

  useEffect(() => {
    void loadList();
  }, [loadList]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{t("nav.discover")}</h1>
        <p className="text-sm text-osap-muted">{t("discover.explain")}</p>
      </div>

      {/* Proveedores de música no cableados (candidatos a conectar) */}
      <Card title={t("discover.providersToConnect")}>
        <Envelope loading={list.loading} error={list.error} data={list.data} emptyMessage={t("discover.nonePending")}>
          {(sources) => {
            const pending = sources.filter((s) => s.status !== "Online");
            if (pending.length === 0) return <p className="text-sm text-osap-muted">{t("discover.nonePending")}</p>;
            return (
              <ul className="divide-y divide-osap-border">
                {pending.map((s) => (
                  <li key={s.source_id} className="flex items-center justify-between py-2">
                    <div>
                      <span className="font-medium">{s.name}</span>
                      <span className="ml-2 text-xs text-osap-muted">
                        {s.type} · {s.origin}
                      </span>
                    </div>
                    <span className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-muted">
                      {s.status}
                    </span>
                  </li>
                ))}
              </ul>
            );
          }}
        </Envelope>
      </Card>

      {/* Fuentes cableadas */}
      <Card title={t("discover.wiredSources")}>
        <Envelope loading={list.loading} error={list.error} data={list.data} emptyMessage={t("discover.noCollections")}>
          {(sources) => {
            const wired = sources.filter((s) => s.status === "Online");
            if (wired.length === 0) return <p className="text-sm text-osap-muted">{t("discover.noCollections")}</p>;
            return (
              <ul className="divide-y divide-osap-border">
                {wired.map((s) => (
                  <li key={s.source_id}>
                    <Link to="/catalog" className="block rounded px-1 py-2 hover:bg-osap-accent-soft">
                      <span className="font-medium">{s.name}</span>
                      <span className="ml-2 text-xs text-osap-muted">
                        {s.type} · {s.origin} · {s.trust}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            );
          }}
        </Envelope>
      </Card>
    </div>
  );
}
