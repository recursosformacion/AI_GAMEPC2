import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { WorkDetail } from "../api/types";
import { Spinner } from "../components/Spinner";
import { WorkDetailTabs } from "../components/WorkDetailTabs";
import { toRepresentations } from "../components/WorksListModule";
import { useI18n } from "../i18n/I18n";

// Página de obra de la app (SPA): la misma experiencia que en los resultados (pestañas,
// representaciones, visor y descarga). La versión indexable sigue en `/obra/{id}/{slug}`
// (SSR); desde aquí se enlaza a ella.
function canonicalWorkId(raw: string): string {
  return raw.startsWith("index-") ? raw : `index-${raw}`;
}

export function WorkPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    setDetail(null);
    // El store de compositores resuelve el id numérico; `index-<n>` es la forma pública.
    apiClient
      .getWork(id.replace(/^index-/, ""))
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <Spinner label={t("states.loading")} />;
  if (failed || detail === null) {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const title = detail.work.title ?? "";
  const canonicalId = canonicalWorkId(id);
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
          {[detail.work.composer, detail.work.catalogue].filter(Boolean).join(" · ")}
        </p>
      </header>
      <WorkDetailTabs
        work={{
          work_id: canonicalId,
          title,
          composer: detail.work.composer ?? null,
          catalogue: detail.work.catalogue ?? null,
        }}
        representations={toRepresentations(detail)}
        score={1}
        allowWorkCorrections
      />
      <p className="text-xs text-osap-muted">
        <a href={`/obra/${canonicalId}`} className="text-osap-accent hover:underline">
          {t("work.viewDetails")}
        </a>
      </p>
    </div>
  );
}
