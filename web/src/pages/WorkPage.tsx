import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { PublicWork, WorkDetail } from "../api/types";
import { Spinner } from "../components/Spinner";
import { WorkDetailTabs } from "../components/WorkDetailTabs";
import { toRepresentations } from "../components/WorksListModule";
import { useI18n } from "../i18n/I18n";

// Página de obra de la app (SPA). Usa la misma experiencia que los resultados (pestañas,
// representaciones, visor y descarga) cuando la obra está en el store de compositores; si
// aún no lo está, muestra la ficha pública del índice (la fuente de la página SEO), con
// descarga directa o «abrir en el proveedor». La versión indexable sigue en `/obra/...`.
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

type State =
  | { kind: "loading" }
  | { kind: "rich"; detail: WorkDetail }
  | { kind: "public"; data: PublicWork }
  | { kind: "missing" };

export function WorkPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    const canonical = canonicalWorkId(id);
    const numeric = canonical.replace(/^index-/, "");
    void (async () => {
      try {
        const detail = await apiClient.getWork(numeric);
        if (!cancelled) setState({ kind: "rich", detail });
        return;
      } catch {
        /* no está en el store de compositores: se usa la ficha pública del índice */
      }
      try {
        const data = await apiClient.getPublicWork(canonical);
        if (!cancelled) setState({ kind: "public", data });
      } catch {
        if (!cancelled) setState({ kind: "missing" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (state.kind === "loading") return <Spinner label={t("states.loading")} />;
  if (state.kind === "missing") {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const canonicalId = canonicalWorkId(id);
  const title = state.kind === "rich" ? (state.detail.work.title ?? "") : state.data.work.title;
  const composer =
    state.kind === "rich" ? (state.detail.work.composer ?? null) : (state.data.work.composer ?? null);
  const catalogue =
    state.kind === "rich" ? (state.detail.work.catalogue ?? null) : (state.data.work.catalogue ?? null);

  return (
    <div className="space-y-4">
      <p className="text-xs text-osap-muted">
        <Link to="/explore" className="text-osap-accent hover:underline">
          ← {t("nav.explore")}
        </Link>
      </p>
      <header>
        <h1 className="text-2xl font-semibold text-osap-ink">{title}</h1>
        <p className="text-sm text-osap-muted">
          {[composer, catalogue].filter(Boolean).join(" · ")}
        </p>
      </header>

      {state.kind === "rich" ? (
        <WorkDetailTabs
          work={{
            work_id: canonicalId,
            title,
            composer,
            catalogue,
          }}
          representations={toRepresentations(state.detail)}
          score={1}
          allowWorkCorrections
        />
      ) : (
        <section className="space-y-2">
          <h2 className="text-base font-semibold text-osap-ink">{t("work.representations")}</h2>
          {state.data.representations.length === 0 ? (
            <p className="text-sm text-osap-muted">{t("work.noResources")}</p>
          ) : (
            <ul className="space-y-1">
              {state.data.representations.map((rep, index) => {
                const site = siteOf(rep.url);
                const label = `${rep.provider} · ${rep.format}`;
                return (
                  <li
                    key={`${rep.provider}-${rep.format}-${index}`}
                    className="flex items-center justify-between gap-2 rounded border border-osap-border bg-osap-surface px-3 py-2 text-sm"
                  >
                    <span className="truncate">{label}</span>
                    {rep.downloadable && rep.url ? (
                      <a
                        href={rep.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 text-osap-accent hover:underline"
                      >
                        {t("work.download")}
                      </a>
                    ) : site ? (
                      <a
                        href={site}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 text-osap-accent hover:underline"
                      >
                        {t("work.openIn").replace("{p}", rep.provider)}
                      </a>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      <p className="text-xs text-osap-muted">
        <a href={`/obra/${canonicalId}`} className="text-osap-accent hover:underline">
          {t("work.publicSheet")}
        </a>
      </p>
    </div>
  );
}
