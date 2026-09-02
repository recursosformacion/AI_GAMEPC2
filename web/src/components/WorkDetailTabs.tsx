import { useState } from "react";
import { Link } from "react-router-dom";
import type { EvidenceInfo, RepresentationInfo, WorkInfo } from "../api/types";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";
import { useResolution } from "../state/resolution";
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
}

function ResolveWorkBlock({
  workTitle,
  workComposer,
  hasUsableFile,
}: {
  workTitle?: string | null;
  workComposer?: string | null;
  hasUsableFile: boolean;
}) {
  const { t } = useI18n();
  const { session, loading, resolve } = useResolution();
  if (!workTitle) return null;

  const startResolve = () => {
    const query = [workTitle, workComposer].filter(Boolean).join(" — ");
    void resolve(query);
  };

  const statusBlock = session ? (
    <div className="mt-2 space-y-2 text-sm">
      <p>
        <span className="text-osap-muted">{t("work.resolveStatus")}:</span>{" "}
        <strong>{session.status}</strong>
        {session.error ? <span className="ml-2 text-xs text-osap-muted">{session.error}</span> : null}
      </p>
      {session.progress?.acquired_works != null ? (
        <p className="text-xs text-osap-muted">
          {t("work.resolveWorks")}: {session.progress.acquired_works} ·{" "}
          {t("work.resolvePages")}: {session.progress.acquired_pages ?? 0}
        </p>
      ) : null}
      {session.selection?.provider ? (
        <div className="rounded border border-osap-border bg-osap-surface p-2">
          <p className="font-medium">
            {t("work.selectedBest")}: {session.selection.provider} · {session.selection.format}
          </p>
          {session.selection.quality_level != null ? (
            <p className="text-xs text-osap-muted">
              {t("work.resolveQuality")}: {session.selection.quality_level}
              {session.selection.quality_score != null
                ? ` · ${t("work.resolveScore")}: ${session.selection.quality_score.toFixed(2)}`
                : ""}
            </p>
          ) : null}
          {session.selection.reason ? (
            <p className="text-xs text-osap-muted">
              {t("work.resolveReason")}: {session.selection.reason}
            </p>
          ) : null}
          {session.selection.url ? (
            <a
              href={session.selection.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-block rounded bg-osap-accent px-2 py-0.5 text-xs text-white"
            >
              {t("actions.download")}
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  ) : null;

  if (!hasUsableFile) {
    return (
      <div className="mt-3 rounded border border-dashed border-osap-border p-3">
        <h4 className="text-sm font-semibold">{t("work.resolveTitle")}</h4>
        <p className="mt-1 text-xs text-osap-muted">{t("work.resolveBody")}</p>
        {!session ? (
          <button
            type="button"
            onClick={startResolve}
            disabled={loading}
            className="mt-2 inline-flex items-center gap-1.5 rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60"
          >
            {loading ? t("states.loading") : t("work.resolveCta")}
          </button>
        ) : (
          statusBlock
        )}
      </div>
    );
  }

  return (
    <div className="mt-3 rounded border border-dashed border-osap-border p-3">
      <h4 className="text-sm font-semibold">{t("work.resolveTitleAlt")}</h4>
      <p className="mt-1 text-xs text-osap-muted">{t("work.resolveBodyAlt")}</p>
      {!session ? (
        <button
          type="button"
          onClick={startResolve}
          disabled={loading}
          className="mt-2 inline-flex items-center gap-1.5 rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60"
        >
          {loading ? t("states.loading") : t("work.resolveCtaAlt")}
        </button>
      ) : (
        statusBlock
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
          </div>
        ) : null}

      {tab === "representations" ? (
        <RepresentationsTab
          representations={representations}
          byProvider={byProvider}
          workTitle={work.title}
          workComposer={work.composer}
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
  workComposer,
}: {
  representations: RepresentationInfo[];
  byProvider: Map<string, RepresentationInfo[]>;
  workTitle?: string | null;
  workComposer?: string | null;
}) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const hasUsableFile = representations.some((r) => r.available);

  return (
    <div className="p-3">
      <p className="mb-2 text-sm text-osap-muted">
        {t("work.foundReps").replace("{n}", String(representations.length)).replace("{p}", String(byProvider.size))}
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
              {rep.url ? (
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
              )}
              {rep.available === false ? (
                <>
                  {rep.url ? (
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
                  )}
                </>
              ) : (
                <>
                  <a
                    href={`/api/v1/representations/${rep.id}/download?view=1`}
                    target="_blank"
                    rel="noreferrer"
                    title={t("work.view")}
                    aria-label={t("work.view")}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1.5 rounded border border-osap-border px-3 py-1 text-sm text-osap-accent"
                  >
                    <_EyeIcon /> {t("work.view")}
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
      <ResolveWorkBlock
        workTitle={workTitle}
        workComposer={workComposer}
        hasUsableFile={hasUsableFile}
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

function downloadFileName(rep: RepresentationInfo, workTitle?: string | null): string {
  const ext = ({ musicxml: "mxl", pdf: "pdf", midi: "mid" } as Record<string, string>)[rep.format] ?? rep.format;
  const base = rep.title || workTitle || rep.id || "representation";
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