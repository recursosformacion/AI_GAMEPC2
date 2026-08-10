import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { ComposerSummary } from "../api/types";
import { useI18n } from "../i18n/I18n";

interface Props {
  placeholder: string;
  onSelect: (composer: ComposerSummary) => void;
  excludeId?: (id: string) => boolean;
}

// Selector de compositores existentes: búsqueda sensible por nombre (y alias si storage la
// soporta), limitada/paginada. Envía composer_id, nunca texto libre.
export function ComposerSearchSelect({ placeholder, onSelect, excludeId }: Props) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<ComposerSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults([]);
      return;
    }
    let active = true;
    setLoading(true);
    apiClient
      .getComposers(term, 20, 0)
      .then((r) => {
        if (active) setResults(r.items);
      })
      .catch(() => {
        if (active) setResults([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [q]);

  const visible = results.filter((r) => !excludeId?.(r.id));

  return (
    <div className="relative">
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="w-full rounded border border-osap-border bg-osap-bg px-3 py-1 text-sm"
      />
      {open && q.trim().length >= 2 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded border border-osap-border bg-osap-surface shadow">
          {loading ? (
            <li className="px-3 py-1 text-sm text-osap-muted">{t("composers.searching")}</li>
          ) : visible.length === 0 ? (
            <li className="px-3 py-1 text-sm text-osap-muted">{t("states.empty")}</li>
          ) : (
            visible.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => {
                    onSelect(c);
                    setQ("");
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between px-3 py-1 text-left text-sm hover:bg-osap-surface"
                >
                  <span className="truncate">{c.name}</span>
                  <span className="shrink-0 text-xs text-osap-muted">{c.works_count}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
