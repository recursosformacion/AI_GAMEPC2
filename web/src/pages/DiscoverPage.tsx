import { useEffect } from "react";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useSources } from "../state/repositorySources";

// Descubrir muestra los proveedores de partituras/música que todavía NO tenemos
// registrados ni cableados (candidatos a añadir como fuente).
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
    </div>
  );
}
