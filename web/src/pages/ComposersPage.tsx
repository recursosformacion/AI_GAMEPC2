import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";

const LIMIT = 50;

export function ComposersPage() {
  const { t } = useI18n();
  const { list, loading, error, q, setQuery, fetchList } = useComposers();
  const [input, setInput] = useState(q);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    void fetchList(q, LIMIT, offset);
  }, [fetchList, q, offset]);

  const search = () => {
    setOffset(0);
    setQuery(input);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("composers.title")}</h1>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder={t("composers.searchPlaceholder")}
          className="w-full rounded border border-osap-border bg-osap-surface px-3 py-1 text-sm"
        />
        <button onClick={search} className="rounded bg-osap-accent px-4 py-1 text-sm text-white">
          {t("search")}
        </button>
      </div>

      <Envelope loading={loading} error={error} data={list} emptyMessage={t("states.empty")}>
        {(data) => (
          <>
            <ul className="divide-y divide-osap-border rounded border border-osap-border">
              {data.items.map((c) => (
                <li key={c.id} className="flex items-center justify-between px-3 py-2">
                  <Link to={`/composers/${encodeURIComponent(c.id)}`} className="font-medium hover:text-osap-accent">
                    {c.name}
                  </Link>
                  <span className="text-xs text-osap-muted">{c.works_count} {t("composers.works")}</span>
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between pt-2 text-sm">
              <button
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
                className="rounded px-3 py-1 disabled:opacity-40"
              >
                {t("pagination.previous")}
              </button>
              <span className="text-xs text-osap-muted">{t("composers.total")}: {data.total}</span>
              <button
                disabled={offset + LIMIT >= data.total}
                onClick={() => setOffset((o) => o + LIMIT)}
                className="rounded px-3 py-1 disabled:opacity-40"
              >
                {t("pagination.next")}
              </button>
            </div>
          </>
        )}
      </Envelope>
    </div>
  );
}
