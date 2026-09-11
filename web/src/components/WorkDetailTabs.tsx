import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { EvidenceInfo, RepresentationInfo, RepresentationSelection, WorkInfo } from "../api/types";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";
import { VoteControl } from "./VoteControl";
import { WorkRating } from "./WorkRating";

export type WorkDetailTab = "overview" | "representations" | "evidence" | "providers";

const TABS: { id: WorkDetailTab; labelKey: string }[] = [
  { id: "overview", labelKey: "work.overview" },
  { id: "representations", labelKey: "work.representations" },
  { id: "evidence", labelKey: "work.evidence" },
  { id: "providers", labelKey: "work.providers" },
];

interface WorkDetailTabsProps {
  work: WorkInfo;
  representations: RepresentationInfo[];
  score: number;
  evidence?: EvidenceInfo[];
  /** Which tab is active initially. Defaults to "representations". */
  defaultTab?: WorkDetailTab;
  /** Solo en el contexto de obras OMR/storage: permite proponer corrección. */
  allowWorkCorrections?: boolean;
}

function KnownSelectionBlock({
  workId,
  representations,
  workTitle,
}: {
  workId?: string | null;
  representations: RepresentationInfo[];
  workTitle?: string | null;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState<RepresentationSelection | null>(null);
  const [error, setError] = useState<string | null>(null);

  const knownCount = representations.length;
  const providersCount = new Set(representations.map((r) => r.provider)).size;
  const inputs = representations
    .filter((r) => r.url)
    .map((r) => ({
      id: r.id,
      provider: r.provider,
      format: r.format,
      url: r.url as string,
      title: r.title ?? null,
    }));

  useEffect(() => {
    if (!workId) return;
    let alive = true;
    apiClient
      .getWorkRepresentationSelection(workId)
      .then((s) => {
        if (alive && s.status === "selected") setSelection(s);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [workId]);

  const runSelection = async () => {
    if (!workId) return;
    setBusy(true);
    setError(null);
    try {
      setSelection(await apiClient.selectBestRepresentation(workId, inputs));
    } catch {
      setError("No se pudo completar la selección.");
    } finally {
      setBusy(false);
    }
  };

  const sel = selection?.selected ?? null;
  const status = selection?.status;

  return (
    <div className="mt-3 rounded border border-dashed border-osap-border p-3">
      <h4 className="text-sm font-semibold">{t("work.resolveTitleAlt")}</h4>
      <p className="mt-1 text-xs text-osap-muted">
        {t("work.foundReps").replace("{n}", String(knownCount)).replace("{p}", String(providersCount))}
      </p>
      <button
        type="button"
        onClick={() => void runSelection()}
        disabled={busy || !workId || knownCount === 0}
        className="mt-2 inline-flex items-center gap-1.5 rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60"
      >
        {busy ? t("states.loading") : t("work.resolveCtaAlt")}
      </button>

      {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}

      {!status ? (
        <p className="mt-2 text-sm text-osap-muted">{t("work.selectNone")}</p>
      ) : status === "selected" && sel ? (
        <div className="mt-2 rounded border border-osap-border bg-osap-surface p-2">
          <p className="text-sm font-medium">
            {t("work.selectHeading")}: {sel.provider ?? "—"} · {sel.format ?? "—"}
          </p>
          {sel.quality_level != null ? (
            <p className="text-xs text-osap-muted">QualityLevel: {sel.quality_level}</p>
          ) : null}
          {sel.reason ? (
            <p className="text-xs text-osap-muted">
              {t("work.resolveReason")}: {sel.reason}
            </p>
          ) : null}
          {sel.source_id || sel.url ? (
            <a
              href={
                sel.source_id
                  ? `/api/v1/representations/${encodeURIComponent(sel.source_id)}/download`
                  : (sel.url as string)
              }
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-block rounded bg-osap-accent px-2 py-0.5 text-xs text-white"
            >
              {t("actions.download")}
            </a>
          ) : null}
          {sel.source_id ? (
            <a
              href={_viewHref(sel.source_id, sel.format, workTitle)}
              target="_blank"
              rel="noreferrer"
              className="mt-1 ml-2 inline-block rounded border border-osap-accent px-2 py-0.5 text-xs text-osap-accent"
            >
              {t("actions.viewScore")}
            </a>
          ) : null}
        </div>
      ) : status === "none_known" ? (
        <p className="mt-2 text-sm text-osap-muted">{t("work.noneKnown")}</p>
      ) : status === "none_selected" ? (
        <p className="mt-2 text-sm text-osap-muted">{t("work.selectNone")}</p>
      ) : (
        <p className="mt-2 text-sm text-osap-muted">
          {t("work.noneUsable")}
          {selection?.errors?.length ? <span className="ml-1 text-xs">({selection.errors.join("; ")})</span> : null}
        </p>
      )}
    </div>
  );
}

export function WorkDetailTabs({
  work,
  representations,
  score,
  evidence: _evidence,
  defaultTab = "representations",
  allowWorkCorrections = false,
}: WorkDetailTabsProps) {
  const { t } = useI18n();
  const isAuthenticated = useAuth((s) => s.isAuthenticated());
  const [tab, setTab] = useState<WorkDetailTab>(defaultTab);

  const byProvider = new Map<string, RepresentationInfo[]>();
  for (const rep of representations) {
    const arr = byProvider.get(rep.provider) ?? [];
    arr.push(rep);
    byProvider.set(rep.provider, arr);
  }

  const providers = new Set(representations.map((r) => r.provider));

  const explainItems: { label: string; value: string }[] = [
    { label: t("why.matchedTitle"), value: work.title },
    { label: t("why.matchedComposer"), value: work.composer ?? "—" },
    { label: t("why.catalogue"), value: work.catalogue ?? "—" },
    { label: t("why.providerAgreement"), value: String(providers.size) },
    { label: t("why.confidence"), value: (score * 100).toFixed(1) + "%" },
  ];

  return (
    <div>
      <div className="flex gap-1 border-b border-osap-border">
        {TABS.map((tb) => (
          <button
            key={tb.id}
            type="button"
            onClick={() => setTab(tb.id)}
            className={`px-3 py-1.5 text-xs ${
              tab === tb.id
                ? "border-b-2 border-osap-accent font-medium text-osap-accent"
                : "text-osap-muted"
            }`}
          >
            {t(tb.labelKey as TKey)}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <div className="p-3">
          <h3 className="text-lg font-semibold">{work.title}</h3>
          <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
            <Meta label={t("work.composer")} value={work.composer ?? "—"} />
            <Meta label={t("work.catalogue")} value={work.catalogue ?? "—"} />
          </dl>
          <Link
            to={`/works/${work.work_id}`}
            className="mt-3 inline-block rounded bg-osap-accent px-3 py-1 text-sm text-white"
          >
            {t("work.viewDetails")}
          </Link>
          <p className="mt-2 text-sm text-osap-muted">
            {representations.length} {t("work.representations")} · {providers.size} {t("work.providers")}
          </p>
          <p className="mt-1 text-sm text-emerald-700">
            ✓ {t("work.consolidated").replace("{p}", String(providers.size))}
            <span className="text-osap-muted">
              {" · "}
              {t("work.matchingConfidence").replace("{c}", (score * 100).toFixed(0) + "%")}
            </span>
          </p>

           {work.work_id ? (
             <div className="mt-4 flex flex-col gap-2 border-t border-osap-border pt-3">
               {isAuthenticated ? (
                 <>
                   <WorkRating workId={work.work_id} />
                   <VoteControl workId={work.work_id} />
                 </>
               ) : (
                 <p className="text-sm text-osap-muted">{t("work.loginToRate")}</p>
               )}
             </div>
            ) : null}

          {allowWorkCorrections && work.work_id ? (
            <Link
              to={`/corrections?kind=work&entity_id=${encodeURIComponent(work.work_id)}`}
              className="mt-2 inline-block rounded border border-osap-accent/40 px-3 py-1 text-sm font-medium text-osap-accent transition-colors hover:border-osap-accent hover:bg-osap-accent-soft"
            >
              {t("corrections.propose")}
            </Link>
          ) : null}
        </div>
        ) : null}

      {tab === "representations" ? (
        <RepresentationsTab
          representations={representations}
          byProvider={byProvider}
          workTitle={work.title}
          workId={work.work_id}
        />
      ) : null}

      {tab === "evidence" ? (
        <div className="p-3">
          <h3 className="text-sm font-semibold">{t("work.whySameWork")}</h3>
          <ul className="mt-2 space-y-1">
            {explainItems.map((e) => (
              <li key={e.label} className="flex justify-between text-sm">
                <span className="text-osap-muted">{e.label}</span>
                <span>{e.value}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-osap-muted">{t("work.confidenceNote")}</p>

          {representations.length > 0 ? (
            <div className="mt-3 border-t border-osap-border pt-2">
              <h4 className="text-xs font-semibold uppercase text-osap-muted">{t("work.evidenceSources")}</h4>
              <ul className="mt-1 space-y-1">
                {[...byProvider.entries()].map(([provider, reps]) => (
                  <li key={provider} className="text-sm">
                    <span className="font-medium">{provider}</span>
                    <span className="ml-2 text-osap-muted">
                      {t("work.title")}: {reps[0]?.title || "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {tab === "providers" ? <ProvidersTab byProvider={byProvider} /> : null}
    </div>
  );
}

function RepresentationsTab({
  representations,
  byProvider,
  workTitle,
  workId,
}: {
  representations: RepresentationInfo[];
  byProvider: Map<string, RepresentationInfo[]>;
  workTitle?: string | null;
  workId?: string | null;
}) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="p-3">
      <p className="mb-2 text-sm text-osap-muted">
        {t("work.foundReps").replace("{n}", String(representations.length)).replace("{p}", String(byProvider.size))}
      </p>
      <p className="mb-2 text-xs text-osap-muted">
        {t("how.downloadsNote")}{" "}
        <Link to="/about/how-it-works#downloads" className="text-osap-accent hover:underline">
          {t("how.accessTitle")}
        </Link>
      </p>

      <ul className="divide-y divide-osap-border">
        {representations.map((rep, i) => (
          <li
            key={`${rep.provider}-${rep.format}-${i}`}
            className={`flex items-center gap-2 px-1 py-1.5 text-sm hover:bg-osap-accent-soft ${
              selected === rep.id ? "bg-osap-accent-soft" : ""
            }`}
            onClick={() => setSelected(rep.id)}
          >
            <span className="min-w-0 flex-1 cursor-pointer text-left">
              <span className="block truncate font-medium">{rep.title || rep.provider}</span>
              <span className="block text-xs text-osap-muted">
                {rep.provider} · {rep.format} · {(rep.confidence * 100).toFixed(0)}%
              </span>
            </span>
            <span className="flex shrink-0 items-center gap-1.5">
              {rep.available === false ? (
                rep.url ? (
                  <a
                    href={rep.url}
                    target="_blank"
                    rel="noreferrer"
                    title={t("work.openIn").replace("{p}", rep.provider)}
                    aria-label={t("work.openIn").replace("{p}", rep.provider)}
                    onClick={(e) => e.stopPropagation()}
                    className="px-1.5 text-osap-muted hover:text-osap-accent"
                  >
                    <_LinkIcon />
                  </a>
                ) : (
                  <span className="px-1 text-xs text-osap-muted">—</span>
                )
              ) : (
                <>
                  <a
                    href={_viewHref(rep.id, rep.format, workTitle)}
                    target="_blank"
                    rel="noreferrer"
                    title={(rep.format ?? "").toLowerCase() === "midi" ? t("actions.playPause") : t("work.view")}
                    aria-label={(rep.format ?? "").toLowerCase() === "midi" ? t("actions.playPause") : t("work.view")}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1.5 rounded border border-osap-border px-3 py-1 text-sm text-osap-accent"
                  >
                    <_EyeIcon />{" "}
                    {(rep.format ?? "").toLowerCase() === "midi" ? t("actions.playPause") : t("work.view")}
                  </a>
                  <a
                    href={`/api/v1/representations/${rep.id}/download`}
                    download={downloadFileName(rep, workTitle)}
                    target="_blank"
                    rel="noreferrer"
                    title={t("work.download")}
                    aria-label={t("work.download")}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1.5 rounded border border-osap-border px-3 py-1 text-sm text-osap-accent"
                  >
                    <_DownloadIcon /> {t("work.download")}
                  </a>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-osap-muted">{t("work.titlesFromSources")}</p>
              <KnownSelectionBlock
                workId={workId}
                representations={representations}
                workTitle={workTitle}
              />
    </div>
  );
}

function ProvidersTab({ byProvider }: { byProvider: Map<string, RepresentationInfo[]> }) {
  const { t } = useI18n();

  return (
    <div className="p-3">
      <p className="mb-2 text-sm text-osap-muted">
        {t("work.appearsIn").replace("{n}", String(byProvider.size))}
      </p>
      <ul className="divide-y divide-osap-border">
        {[...byProvider.entries()].map(([provider, reps]) => {
          const formats = [...new Set(reps.map((r) => r.format))].join(" · ");
          const url = reps.find((r) => r.url)?.url ?? null;
          return (
            <li key={provider} className="flex items-center justify-between py-2 text-sm">
              <div>
                <span className="font-medium">{provider}</span>
                <p className="text-osap-muted">
                  {t("work.repCount").replace("{n}", String(reps.length))} · {formats}
                </p>
              </div>
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-1.5 text-osap-muted hover:text-osap-accent"
                >
                  <_LinkIcon />
                </a>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function _viewHref(repId: string, format: string | null | undefined, workTitle?: string | null): string {
  const fmt = (format ?? "").toLowerCase();
  if (fmt === "midi") {
    return `/viewer?rep=${encodeURIComponent(repId)}&format=midi&title=${encodeURIComponent(workTitle ?? "")}`;
  }
  if (["musicxml", "mxl", "xml", "mei"].includes(fmt)) {
    return `/viewer?rep=${encodeURIComponent(repId)}&title=${encodeURIComponent(workTitle ?? "")}`;
  }
  return `/api/v1/representations/${encodeURIComponent(repId)}/download?view=1`;
}

function downloadFileName(rep: RepresentationInfo, workTitle?: string | null): string {
  const ext = ({ musicxml: "mxl", pdf: "pdf", midi: "mid" } as Record<string, string>)[rep.format] ?? rep.format;
  const base = workTitle || rep.title || rep.id || "representation";
  const safe = base.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "_");
  return `${safe}.${ext}`;
}

const _ICON_CLASS = "h-4 w-4";

function _EyeIcon() {
  return (
    <svg className={_ICON_CLASS} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function _DownloadIcon() {
  return (
    <svg className={_ICON_CLASS} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function _LinkIcon() {
  return (
    <svg className={_ICON_CLASS} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-osap-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}