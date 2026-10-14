import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosEvent } from "../api/types";
import { AmigosNote } from "../components/AmigosNote";
import { Spinner } from "../components/Spinner";
import { useAmigosPermissions } from "../components/useAmigosPermissions";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { formatEuroDate } from "../utils/dates";

const KIND_KEY: Record<string, TKey> = {
  concert: "friends.eventKind.concert",
  meeting: "friends.eventKind.meeting",
  festival: "friends.eventKind.festival",
  workshop: "friends.eventKind.workshop",
  mass: "friends.eventKind.mass",
  competition: "friends.eventKind.competition",
  rehearsal: "friends.eventKind.rehearsal",
  other: "friends.eventKind.other",
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function buyUrl(e: AmigosEvent): string | null {
  return e.tickets_url ?? e.event_url ?? null;
}

// «Próximas actuaciones y eventos»: rejilla de anuncios (imagen entera + fecha/localidad +
// Comprar). Orden y exclusión de pasados los pone el servidor. Filtros por tipo, localidad
// (desplegable alimentado por los anuncios vigentes) y fecha. Se cuentan impresiones (view),
// ampliaciones (expand) y compras (buy).
export function AmigosEventsPage() {
  const { t } = useI18n();
  const [events, setEvents] = useState<AmigosEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState("");
  const [locality, setLocality] = useState("");
  const [date, setDate] = useState("");
  const [open, setOpen] = useState<AmigosEvent | null>(null);
  const seenViews = useRef<Set<string>>(new Set());
  const perms = useAmigosPermissions();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getAmigosEvents({ from_date: today() });
      setEvents(data.items);
    } catch {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Localidades disponibles (de los anuncios vigentes).
  const localities = useMemo(
    () =>
      Array.from(new Set(events.map((e) => e.locality).filter((x): x is string => !!x))).sort(
        (a, b) => a.localeCompare(b),
      ),
    [events],
  );

  const filtered = useMemo(
    () =>
      events.filter(
        (e) =>
          (kind === "" || e.kind === kind) &&
          (locality === "" || e.locality === locality) &&
          (date === "" || e.starts_on === date),
      ),
    [events, kind, locality, date],
  );

  // Impresión: se cuenta una vez por anuncio mostrado.
  useEffect(() => {
    for (const e of filtered) {
      if (!seenViews.current.has(e.id)) {
        seenViews.current.add(e.id);
        apiClient.recordAmigosEvent(e.id, "view");
      }
    }
  }, [filtered]);

  const buy = (e: AmigosEvent) => {
    const url = buyUrl(e);
    if (url === null) return;
    apiClient.recordAmigosEvent(e.id, "buy");
    window.open(url, "_blank", "noopener");
  };

  const expand = (e: AmigosEvent) => {
    apiClient.recordAmigosEvent(e.id, "expand");
    setOpen(e);
  };

  return (
    <div className="space-y-5">
      <header className="border-b border-osap-border pb-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
              {t("nav.sectionFriends")}
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("friends.eventsTitle")}</h1>
          </div>
          {perms?.events ? (
            <Link
              to="/mis/anuncios"
              className="shrink-0 rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white hover:bg-osap-accent/90"
            >
              {t("friends.manageEvents")}
            </Link>
          ) : null}
        </div>
        <AmigosNote titleKey="friends.eventsNoteTitle" bodyKey="friends.eventsNoteBody" />
      </header>

      <div className="flex flex-wrap gap-2">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        >
          <option value="">{t("friends.kind")}: —</option>
          {Object.entries(KIND_KEY).map(([code, key]) => (
            <option key={code} value={code}>
              {t(key)}
            </option>
          ))}
        </select>
        <select
          value={locality}
          onChange={(e) => setLocality(e.target.value)}
          className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        >
          <option value="">{t("friends.locality")}: —</option>
          {localities.map((loc) => (
            <option key={loc} value={loc}>
              {loc}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        />
        {date !== "" || locality !== "" || kind !== "" ? (
          <button
            type="button"
            onClick={() => {
              setKind("");
              setLocality("");
              setDate("");
            }}
            className="rounded-md border border-osap-border px-3 py-2 text-sm"
          >
            ✕
          </button>
        ) : null}
      </div>

      {loading ? (
        <Spinner label={t("states.loading")} />
      ) : filtered.length === 0 ? (
        <p className="text-sm text-osap-muted">{t("friends.eventsEmpty")}</p>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((e) => (
            <li
              key={e.id}
              className="flex flex-col overflow-hidden rounded-card border border-osap-border bg-osap-surface shadow-card"
            >
              <button
                type="button"
                onClick={() => expand(e)}
                aria-label={e.title}
                className="block w-full bg-osap-accent-soft"
              >
                {e.image_url ? (
                  <img src={e.image_url} alt={e.title} className="h-64 w-full object-contain" />
                ) : (
                  <span className="block h-64 w-full" />
                )}
              </button>
              <div className="px-3 py-2 text-sm text-osap-muted">
                {formatEuroDate(e.starts_on)}
                {e.starts_at ? ` · ${e.starts_at}` : ""}
                {e.locality ? ` · ${e.locality}` : ""}
              </div>
              {buyUrl(e) !== null ? (
                <button
                  type="button"
                  onClick={() => buy(e)}
                  className="mt-auto block w-full bg-osap-accent px-3 py-2 text-center text-sm font-medium text-white hover:bg-osap-accent/90"
                >
                  {t("friends.buy")}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {open !== null ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
          onClick={() => setOpen(null)}
        >
          <button
            type="button"
            aria-label={t("friends.close")}
            onClick={() => setOpen(null)}
            className="absolute right-4 top-4 text-3xl leading-none text-white"
          >
            ✕
          </button>
          {open.image_url ? (
            <img
              src={open.image_url}
              alt={open.title}
              onClick={(ev) => {
                ev.stopPropagation();
                buy(open);
              }}
              className="max-h-full max-w-full cursor-pointer object-contain"
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
