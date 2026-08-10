import { useState } from "react";
import type { EvidenceInfo, RepresentationInfo, WorkInfo, WorkRelationships } from "../api/types";
import { useI18n } from "../i18n/I18n";
import { VoteControl } from "./VoteControl";
import { WorkRating } from "./WorkRating";

export type WorkDetailTab = "overview" | "representations" | "evidence" | "relationships";

const TABS: { id: WorkDetailTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "representations", label: "Representations" },
  { id: "evidence", label: "Evidence" },
  { id: "relationships", label: "Relationships" },
];

interface WorkDetailTabsProps {
  work: WorkInfo;
  representations: RepresentationInfo[];
  score: number;
  evidence?: EvidenceInfo[];
  relationships?: WorkRelationships | null;
  /** Which tab is active initially. Defaults to "representations". */
  defaultTab?: WorkDetailTab;
}

export function WorkDetailTabs({
  work,
  representations,
  score,
  evidence,
  relationships,
  defaultTab = "representations",
}: WorkDetailTabsProps) {
  const { t } = useI18n();
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
            {tb.label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <div className="p-3">
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            <Meta label="Catalogue" value={work.catalogue ?? "—"} />
            <Meta label="Composer" value={work.composer ?? "—"} />
            <Meta label="Representations" value={String(representations.length)} />
            <Meta label="Providers" value={String(providers.size)} />
          </dl>
          <p className="mt-3 text-sm text-osap-muted">
            Merge: {representations.length} representation{representations.length === 1 ? "" : "s"} from{" "}
            {providers.size} provider{providers.size === 1 ? "" : "s"} consolidated into this work.
          </p>
          {work.work_id ? (
            <div className="mt-4 flex flex-col gap-2 border-t border-osap-border pt-3">
              <WorkRating workId={work.work_id} />
              <VoteControl workId={work.work_id} />
            </div>
          ) : null}
        </div>
      ) : null}

      {tab === "representations" ? <RepresentationsTab work={work} representations={representations} byProvider={byProvider} /> : null}

      {tab === "evidence" ? (
        <div className="p-3">
          <ul className="space-y-1">
            {explainItems.map((e) => (
              <li key={e.label} className="flex justify-between text-sm">
                <span className="text-osap-muted">{e.label}</span>
                <span>{e.value}</span>
              </li>
            ))}
          </ul>
          {evidence && evidence.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase text-osap-muted">Evidence</h3>
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

      {tab === "relationships" ? <RelationshipsTab relationships={relationships} /> : null}
    </div>
  );
}

function RepresentationsTab({
  work,
  representations,
  byProvider,
}: {
  work: WorkInfo;
  representations: RepresentationInfo[];
  byProvider: Map<string, RepresentationInfo[]>;
}) {
  return (
    <div className="p-3">
      <p className="mb-2 text-sm text-osap-muted">
        {byProvider.size === 1 ? "Only " : ""}
        <strong>{[...byProvider.keys()].join(", ")}</strong>
        {byProvider.size === 1 ? " returned results for this search." : ` (${byProvider.size} providers) matched.`}
      </p>

      {/* Header row (desktop-friendly single-line grid) */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 border-b border-osap-border px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-osap-muted">
        <span>Title</span>
        <span className="w-16 text-right">Format</span>
        <span className="w-20 text-right">Confidence</span>
        <span className="w-24 text-right">Action</span>
      </div>

      <ul className="divide-y divide-osap-border">
        {representations.map((rep, i) => {
          const href = `/api/v1/representations/${rep.id}/download`;
          const ext = ({ musicxml: "mxl", pdf: "pdf", midi: "mid" } as Record<string, string>)[rep.format] ?? rep.format;
          const filename = `${work.title}.${ext}`;
          const title = rep.title || `${rep.provider} · ${rep.format} · ${rep.confidence.toFixed(2)}`;
          return (
            <li key={`${rep.provider}-${rep.format}-${i}`} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 px-1 py-1.5 text-sm">
              <span title={title} className="truncate">
                <span className="font-medium">{title}</span>
              </span>
              <span title={rep.format} className="w-16 text-right text-xs text-osap-muted">
                {rep.format}
              </span>
              <span className="w-20 text-right text-xs text-osap-muted">{rep.confidence.toFixed(2)}</span>
              <span className="flex w-24 items-center justify-end gap-1">
                <a href={href} title="View score" className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-accent">
                  View
                </a>
                <a
                  href={href}
                  download={filename}
                  title={`Download ${filename}`}
                  className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-accent"
                >
                  DL
                </a>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RelationshipsTab({ relationships }: { relationships?: WorkRelationships | null }) {
  return (
    <div className="space-y-4 p-3">
      <div>
        <h3 className="text-xs font-semibold uppercase text-osap-muted">Aliases</h3>
        {relationships && relationships.aliases && relationships.aliases.length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-1">
            {relationships.aliases.map((a) => (
              <span key={a} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                {a}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-sm text-osap-muted">—</p>
        )}
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase text-osap-muted">Related catalogue</h3>
        {relationships && relationships.related_catalogues && relationships.related_catalogues.length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-1">
            {relationships.related_catalogues.map((c) => (
              <span key={c} className="rounded border border-osap-border px-2 py-0.5 text-xs">
                {c}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-sm text-osap-muted">—</p>
        )}
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase text-osap-muted">Different editions</h3>
        <p className="mt-1 text-sm text-osap-muted">Pending (requires edition/publisher metadata).</p>
      </div>
      <div>
        <h3 className="text-xs font-semibold uppercase text-osap-muted">Parent work</h3>
        <p className="mt-1 text-sm text-osap-muted">Pending (Work model).</p>
      </div>
      <div>
        <h3 className="text-xs font-semibold uppercase text-osap-muted">Movements</h3>
        <p className="mt-1 text-sm text-osap-muted">Pending (Work model).</p>
      </div>
    </div>
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
