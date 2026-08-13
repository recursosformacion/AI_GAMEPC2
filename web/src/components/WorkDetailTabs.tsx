import { useState } from "react";
import type { EvidenceInfo, RepresentationInfo, WorkInfo } from "../api/types";
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
}

export function WorkDetailTabs({
  work,
  representations,
  score,
  evidence,
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
            className={`px-3 py-1.5 text-xs ${tab === tb.id ? "border-b-2 border-osap-accent font-medium text-osap-accent" : "text-osap-muted"}`}
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

      {tab === "representations" ? <RepresentationsTab representations={representations} byProvider={byProvider} /> : null}

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

          {evidence && evidence.length > 0 ? (
            <div className="mt-3">
              <h4 className="text-xs font-semibold uppercase text-osap-muted">Evidence</h4>
              <ul className="mt-1 space-y-1">
                {evidence.map((ev, i) => (
                  <li key={`${ev.source}-${i}`} className="flex justify-between text-sm">
                    <span className="text-osap-muted">
                      {ev.source} · <code className="text-osap-ink">{ev.code}</code>
                    </span>
                    <span>{(ev.score * 100).toFixed(0)}%</span>
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
}: {
  representations: RepresentationInfo[];
  byProvider: Map<string, RepresentationInfo[]>;
}) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const sel = representations.find((r) => r.id === selected) ?? null;

  return (
    <div className="p-3">
      <p className="mb-2 text-sm text-osap-muted">
        {t("work.foundReps").replace("{n}", String(representations.length)).replace("{p}", String(byProvider.size))}
      </p>

      <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 border-b border-osap-border px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-osap-muted">
        <span>{t("work.title")}</span>
        <span className="w-12 text-right">{t("work.provider")}</span>
        <span className="w-12 text-right">{t("work.format")}</span>
        <span className="w-9 text-right">{t("work.confidence")}</span>
      </div>

      <ul className="divide-y divide-osap-border">
        {representations.map((rep, i) => (
          <li
            key={`${rep.provider}-${rep.format}-${i}`}
            className={`grid grid-cols-[1fr_auto_auto_auto] cursor-pointer items-center gap-2 px-1 py-1.5 text-sm hover:bg-osap-accent-soft ${
              selected === rep.id ? "bg-osap-accent-soft" : ""
            }`}
            onClick={() => setSelected(rep.id)}
          >
            <span title={rep.title || rep.provider} className="truncate">
              <span className="font-medium">{rep.title || rep.provider}</span>
            </span>
            <span title={rep.provider} className="w-12 truncate text-right text-xs text-osap-muted">
              {providerAbbrev(rep.provider)}
            </span>
            <span title={rep.format} className="w-12 text-right text-xs text-osap-muted">
              {rep.format}
            </span>
            <span className="w-9 text-right text-xs text-osap-muted">{(rep.confidence * 100).toFixed(0)}%</span>
          </li>
        ))}
      </ul>

      <p className="mt-2 text-xs text-osap-muted">{t("work.titlesFromSources")}</p>

      {sel ? (
        <div className="mt-3 rounded border border-osap-border bg-osap-surface p-3">
          <h4 className="text-sm font-semibold">{t("work.repDetails")}</h4>
          <dl className="mt-2 space-y-1 text-sm">
            <Meta label={t("work.provider")} value={sel.provider} />
            <Meta label={t("work.originalTitle")} value={sel.title || "—"} />
            <Meta label={t("work.format")} value={sel.format} />
            <Meta label={t("work.providerId")} value={sel.id} />
          </dl>
          <div className="mt-3 flex flex-wrap gap-2">
            {sel.url ? (
              <a
                href={sel.url}
                target="_blank"
                rel="noreferrer"
                className="rounded bg-osap-accent px-3 py-1 text-sm text-white"
              >
                {t("work.openIn").replace("{p}", sel.provider)}
              </a>
            ) : null}
            <a
              href={`/api/v1/representations/${sel.id}/download?view=1`}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-osap-border px-3 py-1 text-sm text-osap-accent"
            >
              {t("work.view")}
            </a>
            <a
              href={`/api/v1/representations/${sel.id}/download`}
              download={downloadFileName(sel)}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-osap-border px-3 py-1 text-sm text-osap-accent"
            >
              {t("work.download")}
            </a>
          </div>
        </div>
      ) : null}
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
                <p className="text-xs text-osap-muted">
                  {t("work.repCount").replace("{n}", String(reps.length))} · {formats}
                </p>
              </div>
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-accent"
                >
                  {t("work.seeSource")}
                </a>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function providerAbbrev(name: string): string {
  const clean = name.trim();
  return clean.length <= 5 ? clean : clean.slice(0, 5);
}

function downloadFileName(rep: RepresentationInfo): string {
  const ext = ({ musicxml: "mxl", pdf: "pdf", midi: "mid" } as Record<string, string>)[rep.format] ?? rep.format;
  const base = rep.title || rep.id || "representation";
  const safe = base.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "_");
  return `${safe}.${ext}`;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-osap-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
