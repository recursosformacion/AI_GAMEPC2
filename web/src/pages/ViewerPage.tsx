// Página "Viewer": visualiza en el navegador un PDF (inline) o un MusicXML (.xml/.mxl)
// con OpenSheetMusicDisplay. Se abre en pestaña nueva desde la ficha de obra.

import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import { loadJSZip, loadOsmd, looksLikeZip, musicXmlFromMxl } from "../viewer/osmdLoader";

type State = "loading" | "rendering" | "ready" | "error" | "pdf";

export function ViewerPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const rep = params.get("rep");
  const title = params.get("title") ?? "";
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    let alive = true;
    if (!rep) {
      setState("error");
      setMessage(t("viewer.missing"));
      return;
    }
    const run = async () => {
      try {
        const response = await apiClient.fetchRepresentationFile(rep);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const contentType = response.headers.get("content-type") ?? "";
        if (contentType.startsWith("application/pdf")) {
          if (!alive) return;
          setState("pdf");
          return;
        }
        const buffer = await response.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let xml: string;
        if (looksLikeZip(bytes)) {
          xml = await musicXmlFromMxl(await loadJSZip(), buffer);
        } else {
          xml = new TextDecoder("utf-8").decode(bytes);
        }
        if (!alive) return;
        setState("rendering");
        const OSMD = await loadOsmd();
        if (!containerRef.current || !alive) return;
        const osmd = new OSMD(containerRef.current, { autoResize: true, backend: "svg" });
        await osmd.load(xml);
        osmd.render();
        if (alive) setState("ready");
      } catch (error) {
        if (!alive) return;
        setState("error");
        setMessage(error instanceof Error ? error.message : String(error));
      }
    };
    void run();
    return () => {
      alive = false;
    };
  }, [rep, t]);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{title || t("viewer.title")}</h1>
        {rep ? (
          <a
            className="text-sm text-osap-accent hover:underline"
            href={`/api/v1/representations/${encodeURIComponent(rep)}/download`}
          >
            {t("actions.download")}
          </a>
        ) : null}
      </div>

      {state === "pdf" && rep ? (
        <iframe
          title={title || "PDF"}
          src={`/api/v1/representations/${encodeURIComponent(rep)}/download?view=1`}
          className="h-[80vh] w-full rounded border border-osap-border"
        />
      ) : null}

      {state === "loading" || state === "rendering" ? (
        <p className="text-sm text-osap-muted">{t("viewer.loading")}</p>
      ) : null}

      {state === "error" ? (
        <div className="rounded border border-osap-border bg-osap-surface p-4 text-sm">
          <p className="text-red-600">{t("viewer.error")}</p>
          {message ? <p className="mt-1 text-osap-muted">{message}</p> : null}
          <Link to="/" className="mt-2 inline-block text-osap-accent hover:underline">
            ← {t("nav.home")}
          </Link>
        </div>
      ) : null}

      <div ref={containerRef} className="overflow-x-auto" />
    </div>
  );
}
