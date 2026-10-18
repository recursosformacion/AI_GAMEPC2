import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { PublicWork, PublicWorkRepresentation } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";

// Página de obra de la app. Usa la **ficha pública del índice** (`index-<n>`), la misma
// fuente que la página SSR: `/works/{id}` (store de compositores) usa OTRO espacio de ids y
// devolvía otra obra para el mismo número.
function canonicalWorkId(raw: string): string {
  return raw.startsWith("index-") ? raw : `index-${raw}`;
}

function siteOf(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.host}/`;
  } catch {
    return null;
  }
}

function viewerHref(rep: PublicWorkRepresentation): string | null {
  if (!rep.downloadable || !rep.id) return null;
  const fmt = rep.format.toLowerCase();
  if (fmt === "midi") return `/viewer?rep=${encodeURIComponent(rep.id)}&format=midi`;
  if (["musicxml", "mxl", "xml", "mei", "pdf"].includes(fmt)) {
    return `/viewer?rep=${encodeURIComponent(rep.id)}`;
  }
  return null;
}

export function WorkPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const [sheet, setSheet] = useState<PublicWork | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing">("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    apiClient
      .getPublicWork(canonicalWorkId(id))
      .then((data) => {
        if (cancelled) return;
        setSheet(data);
        setState("ok");
      })
      .catch(() => {
        if (!cancelled) setState("missing");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (state === "loading") return <Spinner label={t("states.loading")} />;
  if (state === "missing" || sheet === null) {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const canonicalId = canonicalWorkId(id);
  return (
    <div className="space-y-4">
      <p className="text-xs text-osap-muted">
        <Link to="/explore" className="text-osap-accent hover:underline">
          ← {t("nav.explore")}
        </Link>
      </p>
      <header>
        <h1 className="text-2xl font-semibold text-osap-ink">{sheet.work.title}</h1>
        <p className="text-sm text-osap-muted">
          {[sheet.work.composer, sheet.work.catalogue].filter(Boolean).join(" · ")}
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-base font-semibold text-osap-ink">{t("work.representations")}</h2>
        {sheet.representations.length === 0 ? (
          <p className="text-sm text-osap-muted">{t("work.noResources")}</p>
        ) : (
          <ul className="space-y-1">
            {sheet.representations.map((rep, index) => {
              const viewer = viewerHref(rep);
              const site = siteOf(rep.url);
              return (
                <li
                  key={rep.id ?? `${rep.provider}-${rep.format}-${index}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-osap-border bg-osap-surface px-3 py-2 text-sm"
                >
                  <span className="truncate">
                    {rep.id ? (
                      <Link
                        to={`/representacion/${encodeURIComponent(rep.id)}`}
                        className="text-osap-accent hover:underline"
                      >
                        {rep.provider} · {rep.format}
                      </Link>
                    ) : (
                      `${rep.provider} · ${rep.format}`
                    )}
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {viewer ? (
                      <Link to={viewer} className="text-osap-accent hover:underline">
                        {t("actions.viewScore")}
                      </Link>
                    ) : null}
                    {rep.downloadable && rep.url ? (
                      <a
                        href={rep.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-osap-accent hover:underline"
                      >
                        {t("actions.download")}
                      </a>
                    ) : site ? (
                      <a
                        href={site}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-osap-accent hover:underline"
                      >
                        {t("work.openIn").replace("{p}", rep.provider)}
                      </a>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <p className="text-xs text-osap-muted">
        <a href={`/obras/${canonicalId}`} className="text-osap-accent hover:underline">
          {t("work.publicSheet")}
        </a>
      </p>
    </div>
  );
}
