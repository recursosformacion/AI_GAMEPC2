import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { RepresentationSheet } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";

// Página de una representación (SPA): misma URL canónica que la SSR `/representacion/<id>`,
// con acciones útiles: visor (si hay fichero servible), descarga y enlace a la obra.
function viewerHref(sheet: RepresentationSheet): string | null {
  if (!sheet.download_url) return null;
  const fmt = sheet.format.toLowerCase();
  if (fmt === "midi") {
    return `/viewer?rep=${encodeURIComponent(sheet.id)}&format=midi&title=${encodeURIComponent(sheet.title)}`;
  }
  if (["musicxml", "mxl", "xml", "mei"].includes(fmt)) {
    return `/viewer?rep=${encodeURIComponent(sheet.id)}&title=${encodeURIComponent(sheet.title)}`;
  }
  return null;
}

function appWorkPath(workId: string): string {
  return `/obras/${encodeURIComponent(workId.replace(/^index-/, ""))}`;
}

export function RepresentationPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const [sheet, setSheet] = useState<RepresentationSheet | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing">("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    apiClient
      .getRepresentation(id)
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

  const viewer = viewerHref(sheet);
  return (
    <div className="space-y-4">
      <p className="text-xs text-osap-muted">
        <Link to={appWorkPath(sheet.work_id)} className="text-osap-accent hover:underline">
          ← {sheet.title}
        </Link>
      </p>
      <header>
        <h1 className="text-2xl font-semibold text-osap-ink">{sheet.title}</h1>
        <p className="text-sm text-osap-muted">
          {[sheet.composer, sheet.catalogue].filter(Boolean).join(" · ")}
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-osap-border px-2 py-0.5 text-xs">{sheet.provider}</span>
        <span className="rounded border border-osap-border px-2 py-0.5 text-xs">{sheet.format}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {viewer ? (
          <Link to={viewer} className="rounded bg-osap-accent px-3 py-1.5 text-sm text-white">
            {t("actions.viewScore")}
          </Link>
        ) : null}
        {sheet.download_url ? (
          <a
            href={sheet.download_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded border border-osap-accent px-3 py-1.5 text-sm text-osap-accent"
          >
            {t("actions.download")}
          </a>
        ) : sheet.site ? (
          <a
            href={sheet.site}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded border border-osap-accent px-3 py-1.5 text-sm text-osap-accent"
          >
            {t("work.openIn").replace("{p}", sheet.provider)}
          </a>
        ) : null}
      </div>

      <p className="text-xs text-osap-muted">
        <a href={sheet.canonical_url} className="text-osap-accent hover:underline">
          {t("work.publicSheet")}
        </a>
      </p>
    </div>
  );
}
