import { useEffect } from "react";
import { Envelope } from "../components/Envelope";
import { ResultList } from "../components/ResultList";
import { useI18n } from "../i18n/I18n";
import { useObservations, useFacts, useSuggestions } from "../state/knowledge";

export function ObservationsPage() {
  const { t } = useI18n();
  const { data, loading, error, load } = useObservations();
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("knowledge.observedAliases")}</h1>
      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(items) => (
          <ResultList
            items={items}
            keyOf={(o) => `${o.execution_id}-${o.field}-${o.value}`}
            renderItem={(o) => (
              <span>
                {o.source}: {o.field}={o.value}
                {o.provider ? ` (@${o.provider})` : ""}
              </span>
            )}
          />
        )}
      </Envelope>
    </div>
  );
}

export function FactsPage() {
  const { t } = useI18n();
  const { data, loading, error, load } = useFacts();
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("knowledge.providerConsistency")}</h1>
      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(items) => (
          <ResultList
            items={items}
            keyOf={(f) => `${f.fact_type}-${f.field}-${f.value}`}
            renderItem={(f) => (
              <span>
                {f.fact_type}: {f.field}={f.value} ({f.count})
              </span>
            )}
          />
        )}
      </Envelope>
    </div>
  );
}

export function SuggestionsPage() {
  const { t } = useI18n();
  const { data, loading, error, load } = useSuggestions();
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("knowledge.suggestedAliases")}</h1>
      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(items) => (
          <ResultList
            items={items}
            keyOf={(s) => `${s.field}-${s.source_value}`}
            renderItem={(s) => (
              <span>
                {s.suggestion_type}: {s.source_value} → {s.target_value} ({s.reason})
              </span>
            )}
          />
        )}
      </Envelope>
    </div>
  );
}
