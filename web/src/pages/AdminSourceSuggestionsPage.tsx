import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import type { SourceSuggestion } from "../api/types";
import { useI18n } from "../i18n/I18n";

export function AdminSourceSuggestionsPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<SourceSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await apiClient.listSourceSuggestions());
      setError(null);
    } catch {
      setError(t("sources.loadSuggestionsFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const resolve = async (s: SourceSuggestion, action: string) => {
    try {
      await apiClient.resolveSourceSuggestion(s.id, action, messages[s.id] ?? "");
      await load();
    } catch {
      setError(t("sources.resolveFailed"));
    }
  };

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("sources.suggestionsTitle")}</h1>
      {items.length === 0 && <p className="text-sm text-osap-muted">{t("sources.noSuggestions")}</p>}
      {items.map((s) => (
        <Card key={s.id} title={`${s.name} · ${s.status}`}>
          <p className="text-xs text-osap-muted">
            {t("sources.type")}: {s.type} · {t("sources.connection")}: {s.location}
          </p>
          <p className="text-xs text-osap-muted">
            {t("sources.requestedBy")}: {s.requested_by}
          </p>
          <div className="mt-2 flex flex-wrap gap-1">
            {Object.entries(s.mapping).map(([k, v]) => (
              <code key={k} className="rounded bg-osap-accent-soft px-1.5 py-0.5 text-xs">
                {k} → {String(v)}
              </code>
            ))}
          </div>
          {s.admin_message ? <p className="mt-2 text-sm text-osap-muted">{s.admin_message}</p> : null}
          {s.status === "pending" && (
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <input
                value={messages[s.id] ?? ""}
                onChange={(e) => setMessages({ ...messages, [s.id]: e.target.value })}
                placeholder={t("sources.messagePlaceholder")}
                className="min-w-40 flex-1 rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
              />
              <button
                onClick={() => resolve(s, "approve")}
                className="rounded bg-green-600 px-4 py-1.5 text-sm text-white"
              >
                {t("sources.approve")}
              </button>
              <button
                onClick={() => resolve(s, "cancel")}
                className="rounded bg-red-600 px-4 py-1.5 text-sm text-white"
              >
                {t("sources.cancel")}
              </button>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
