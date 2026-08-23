import { useEffect } from "react";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useProviders } from "../state/providers";

// Descubrir muestra los proveedores de partituras/música que todavía NO tenemos
// cableados (candidatos a añadir como fuente), con su descripción localizada.
export function DiscoverPage() {
  const { t, lang } = useI18n();
  const { data, loading, error, list } = useProviders();

  useEffect(() => {
    void list();
  }, [list]);

  const descOf = (p: { description?: Record<string, string> | string | null }): string => {
    const d = p.description;
    if (d && typeof d === "object") {
      return d[lang] ?? d.en ?? d.es ?? "";
    }
    if (typeof d === "string") return d;
    return "";
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{t("nav.discover")}</h1>
        <p className="text-sm text-osap-muted">{t("discover.explain")}</p>
      </div>

      <Card title={t("discover.providersToConnect")}>
        <Envelope loading={loading} error={error} data={data} emptyMessage={t("discover.nonePending")}>
          {(providers) => {
            const pending = providers.filter((p) => !p.available);
            if (pending.length === 0) {
              return <p className="text-sm text-osap-muted">{t("discover.nonePending")}</p>;
            }
            return (
              <ul className="divide-y divide-osap-border">
                {pending.map((p) => (
                  <li key={p.provider_id} className="flex items-center justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="font-medium">{p.name}</span>
                        <span className="font-mono text-xs text-osap-muted">{p.provider_id}</span>
                      </div>
                      {descOf(p) ? <p className="mt-0.5 text-xs text-osap-muted">{descOf(p)}</p> : null}
                      {p.formats.length > 0 ? (
                        <p className="mt-1 text-xs text-osap-muted">
                          {p.formats.join(", ")}
                        </p>
                      ) : null}
                    </div>
                    <span className="shrink-0 rounded border border-osap-border px-2 py-0.5 text-xs text-osap-muted">
                      {t("providers.offline")}
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
