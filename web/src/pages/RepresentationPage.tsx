import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { RepresentationSheet } from "../api/types";
import { Spinner } from "../components/Spinner";
import { RepresentationActions } from "../components/RepresentationActions";
import { VideosLink } from "../components/VideosLink";
import { useI18n } from "../i18n/I18n";

// Página de una representación (SPA): misma URL canónica que la SSR `/representacion/<id>`.
// Si el fichero es servible (propio o externo legible por el servidor) se ofrece el visor;
// si el proveedor pone un reto anti-bot (CPDL/Cloudflare) se ofrece abrirlo en el navegador.
function appWorkPath(workId: string): string {
  return `/obras/${encodeURIComponent(workId.replace(/^index-/, ""))}`;
}

export function RepresentationPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const [sheet, setSheet] = useState<RepresentationSheet | null>(null);
  const [probe, setProbe] = useState<boolean | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing">("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setProbe(null);
    apiClient
      .getRepresentation(id)
      .then((data) => {
        if (cancelled) return;
        setSheet(data);
        setState("ok");
        // Sin fichero propio: sondea si el servidor puede leer el externo (para el visor).
        if (!data.download_url && data.site) {
          apiClient
            .probeRepresentation(id)
            .then((result) => {
              if (!cancelled) setProbe(result.readable);
            })
            .catch(() => {
              if (!cancelled) setProbe(false);
            });
        }
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

  const actionRepresentation = {
    id: sheet.id,
    provider: sheet.provider,
    format: sheet.format,
    url: sheet.site,
    downloadable:
      Boolean(sheet.download_url) || sheet.provider.toLowerCase() === "omr" || probe === true,
    available: Boolean(sheet.download_url) || probe === true,
  };
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
        <VideosLink
          workId={sheet.work_id}
          title={sheet.title}
          composer={sheet.composer}
          resourceId={sheet.id}
          variant="compact"
          label="Vídeos"
        />
      </div>

      <RepresentationActions
        representation={actionRepresentation}
        workTitle={sheet.title}
        variant="buttons"
        labels={{
          view: t("actions.viewScore"),
          download: t("actions.download"),
          open: `${t("work.openIn")} · ${sheet.format}`,
        }}
      />

      {!sheet.download_url && probe === false ? (
        <p className="text-xs text-osap-muted">{t("work.externalChallenge")}</p>
      ) : null}

      <p className="text-xs text-osap-muted">
        <a href={sheet.canonical_url} className="text-osap-accent hover:underline">
          {t("work.publicSheet")}
        </a>
      </p>
    </div>
  );
}
