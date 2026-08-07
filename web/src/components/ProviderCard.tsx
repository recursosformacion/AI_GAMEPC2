import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18n";
import type { ProviderResponse } from "../api/types";
import { Card } from "./Card";

export function ProviderCard({ provider }: { provider: ProviderResponse }): ReactNode {
  const { t } = useI18n();
  return (
    <Card title={provider.name}>
      <div className="flex items-center gap-1 text-sm">
        <span className={provider.available ? "text-osap-success" : "text-osap-danger"}>
          {provider.available ? "✓" : "✗"}
        </span>
        <span>{provider.available ? t("providers.online") : t("providers.offline")}</span>
      </div>
      <p className="mt-2 text-xs text-osap-muted">{t("providers.capabilities")}</p>
      <ul className="mt-1 flex flex-wrap gap-1">
        {provider.formats.map((f) => (
          <li key={f} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
            {f}
          </li>
        ))}
      </ul>
    </Card>
  );
}
