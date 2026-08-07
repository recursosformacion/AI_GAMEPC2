import { useEffect } from "react";
import { Envelope } from "../components/Envelope";
import { ProviderCard } from "../components/ProviderCard";
import { useI18n } from "../i18n/I18n";
import { useProviders } from "../state/providers";

export function ProvidersPage() {
  const { t } = useI18n();
  const { data, loading, error, list } = useProviders();
  useEffect(() => {
    void list();
  }, [list]);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("nav.admin")} — Providers</h1>
      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(providers) => (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {providers.map((p) => (
              <ProviderCard key={p.provider_id} provider={p} />
            ))}
          </div>
        )}
      </Envelope>
    </div>
  );
}
