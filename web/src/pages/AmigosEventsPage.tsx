import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { AmigosEvent } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";

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

// «Próximas actuaciones y eventos»: agenda pública. Muestra los eventos futuros ordenados por
// fecha, con los datos del evento y un enlace a la información oficial del organizador.
export function AmigosEventsPage() {
  const { t } = useI18n();
  const [events, setEvents] = useState<AmigosEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState("");
  const [locality, setLocality] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getAmigosEvents({
        kind: kind === "" ? undefined : kind,
        locality: locality.trim() === "" ? undefined : locality.trim(),
        from_date: today(),
      });
      setEvents(data.items);
    } catch {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [kind, locality]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-5">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("nav.sectionFriends")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("friends.eventsTitle")}</h1>
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
        <input
          value={locality}
          onChange={(e) => setLocality(e.target.value)}
          placeholder={t("friends.locality")}
          className="min-w-48 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        />
      </div>

      {loading ? (
        <Spinner label={t("states.loading")} />
      ) : events.length === 0 ? (
        <p className="text-sm text-osap-muted">{t("friends.eventsEmpty")}</p>
      ) : (
        <ul className="space-y-3">
          {events.map((e) => (
            <li
              key={e.id}
              className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="font-display text-lg font-semibold text-osap-ink">{e.title}</h2>
                <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">
                  {t(KIND_KEY[e.kind] ?? "friends.eventKind.other")}
                </span>
              </div>
              <p className="mt-1 text-sm text-osap-muted">
                {e.starts_on}
                {e.starts_at ? ` · ${e.starts_at}` : ""}
                {e.locality ? ` · ${e.locality}` : ""}
                {e.event_status === "postponed"
                  ? ` · ${t("friends.eventStatus.postponed")}`
                  : e.event_status === "cancelled"
                    ? ` · ${t("friends.eventStatus.cancelled")}`
                    : ""}
              </p>
              {e.summary ? <p className="mt-2 text-sm">{e.summary}</p> : null}
              <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                {e.organizer_name ? (
                  <span className="text-osap-muted">
                    {t("friends.eventOrganizer")}: {e.organizer_name}
                  </span>
                ) : null}
                {e.event_url ?? e.organizer_website ? (
                  <a
                    href={(e.event_url ?? e.organizer_website) as string}
                    rel="nofollow noopener"
                    target="_blank"
                    className="text-osap-accent hover:underline"
                  >
                    {t("friends.eventInfo")} ↗
                  </a>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
