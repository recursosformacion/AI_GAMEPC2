import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { RepresentationInfo, SearchResultItem } from "../api/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import { useSearches } from "../state/searches";

interface Candidate {
  work: SearchResultItem["work"];
  score: number;
  items: SearchResultItem[];
}

type Tab = "overview" | "representations" | "evidence" | "relationships";

function stars(score: number): string {
  const filled = Math.max(1, Math.min(5, Math.round(score * 5)));
  return "★".repeat(filled) + "☆".repeat(5 - filled);
}

function groupCandidates(results: SearchResultItem[]): Candidate[] {
  const byWork = new Map<string, Candidate>();
  for (const item of results) {
    const key = item.work.work_id;
    const existing = byWork.get(key);
    if (existing) {
      existing.items.push(item);
      existing.score = Math.max(existing.score, item.score);
    } else {
      byWork.set(key, { work: item.work, score: item.score, items: [item] });
    }
  }
  return [...byWork.values()].sort((a, b) => b.score - a.score);
}

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "representations", label: "Representations" },
  { id: "evidence", label: "Evidence" },
  { id: "relationships", label: "Relationships" },
];

export function WorkResolutionPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const searchIdParam = searchParams.get("search_id");
  const workParam = searchParams.get("work");
  const data = useSearches((s) => s.data);
  const loading = useSearches((s) => s.loading);
  const error = useSearches((s) => s.error);
  const selectedWorkId = useSearches((s) => s.selectedWorkId);
  const [tab, setTab] = useState<Tab>("overview");

  // Opened in a new tab: load the stored search by id and select the requested work.
  useEffect(() => {
    if (searchIdParam) {
      void useSearches.getState().get(searchIdParam).then(() => {
        if (workParam) useSearches.getState().selectWork(workParam);
      });
    }
  }, [searchIdParam, workParam]);

  if (loading) {
    return <Spinner label={t("states.loading")} />;
  }
  if (error !== null || data === null || data.results.length === 0) {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const candidates = groupCandidates(data.results);
  const top =
    (selectedWorkId ? candidates.find((c) => c.work.work_id === selectedWorkId) : undefined) ?? candidates[0];
  if (top === undefined) {
    return <EmptyState message={t("states.empty")} />;
  }

  const reps: RepresentationInfo[] = top.items[0]?.representations ?? top.items.map((i) => i.representation);
  const relationships = top.items[0]?.relationships;
  const byProvider = new Map<string, RepresentationInfo[]>();
  for (const rep of reps) {
    const arr = byProvider.get(rep.provider) ?? [];
    arr.push(rep);
    byProvider.set(rep.provider, arr);
  }

  const formats = new Set(reps.map((r) => r.format));

  const explainItems: { label: string; value: string }[] = [
    { label: t("why.matchedTitle"), value: top.work.title },
    { label: t("why.matchedComposer"), value: top.work.composer ?? "—" },
    { label: t("why.catalogue"), value: top.work.catalogue ?? "—" },
    { label: t("why.providerAgreement"), value: String(byProvider.size) },
    { label: t("why.confidence"), value: (top.score * 100).toFixed(1) + "%" },
  ];

  return (
    <div className="space-y-4">
      <button type="button" onClick={() => navigate(-1)} className="text-sm text-osap-accent">
        ← Back to works
      </button>
      {/* Header — resolved work */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-osap-success">✓</span>
              <h1 className="text-xl font-semibold">
                {top.work.composer ? `${top.work.composer} — ` : ""}
                {top.work.title}
              </h1>
            </div>
            <p className="text-sm text-osap-muted">
              {stars(top.score)} {t("resolution.confidence")}: {(top.score * 100).toFixed(1)}% ·{" "}
              {t("resolution.representations")}: {reps.length} · {t("resolution.providers")}: {byProvider.size}
            </p>
          </div>
          {reps.length > 1 ? (
            <p className="text-xs text-osap-muted">
              Formats: {[...formats].join(" · ")}
            </p>
          ) : null}
        </div>
      </Card>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-osap-border">
        {TABS.map((tb) => (
          <button
            key={tb.id}
            type="button"
            onClick={() => setTab(tb.id)}
            className={`px-3 py-2 text-sm ${tab === tb.id ? "border-b-2 border-osap-accent font-medium text-osap-accent" : "text-osap-muted"}`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <Card>
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            <Meta label="Catalogue" value={top.work.catalogue ?? "—"} />
            <Meta label="Composer" value={top.work.composer ?? "—"} />
            <Meta label="Representations" value={String(reps.length)} />
            <Meta label="Providers" value={String(byProvider.size)} />
          </dl>

          <p className="mt-3 text-sm text-osap-muted">
            Merge: {reps.length} representation{reps.length === 1 ? "" : "s"} from{" "}
            {byProvider.size} provider{byProvider.size === 1 ? "" : "s"} consolidated into this work.
          </p>

          {reps.length > 1 ? (
            <div className="mt-4 rounded bg-osap-accent-soft p-3 text-sm">
              <p className="font-medium text-osap-accent">Automatic summary</p>
              <p className="mt-1 text-osap-muted">
                This work has {reps.length} representation{reps.length === 1 ? "" : "s"} across{" "}
                {byProvider.size} provider{byProvider.size === 1 ? "" : "s"}.
              </p>
              <ul className="mt-1 space-y-0.5 text-osap-muted">
                <li>
                  Most complete representation: <strong>{[...byProvider.keys()][0]}</strong>
                </li>
                <li>
                  Highest confidence: <strong>{top.score.toFixed(3)}</strong>
                </li>
              </ul>
            </div>
          ) : null}
        </Card>
      ) : null}

      {tab === "representations" ? (
        <Card title={t("resolution.representations")}>
          {byProvider.size === 1 ? (
            <p className="mb-2 text-sm text-osap-muted">
              Only <strong>{[...byProvider.keys()][0]}</strong> returned results for this search. Other providers may
              not have matched or were not reached.
            </p>
          ) : (
            <p className="mb-2 text-sm text-osap-muted">{byProvider.size} providers matched.</p>
          )}
          <ul className="space-y-2">
            {[...byProvider.entries()].map(([provider, providerReps]) => (
              <li key={provider} className="rounded border border-osap-border p-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{provider}</span>
                  <span className="text-sm text-osap-muted">{providerReps.length} rep(s)</span>
                </div>
                <div className="mt-1 flex flex-col gap-1">
                  {providerReps.map((rep, i) => {
                    const ext = ({ musicxml: "mxl", pdf: "pdf", midi: "mid" } as Record<string, string>)[rep.format] ?? rep.format;
                    const filename = `${top.work.title}.${ext}`;
                    const href = `/api/v1/representations/${rep.id}/download`;
                    return (
                      <div key={`${provider}-${rep.format}-${i}`} className="flex flex-wrap items-center gap-2">
                        <span className="text-sm">{rep.title || `${rep.format} · ${rep.confidence.toFixed(2)}`}</span>
                        <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                          {rep.format} · {rep.confidence.toFixed(2)}
                        </span>
                        <a href={href} target="_blank" rel="noopener noreferrer" className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-accent">
                          View
                        </a>
                        <a
                          href={href}
                          download={filename}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-accent"
                        >
                          Download
                        </a>
                      </div>
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {tab === "evidence" ? (
        <Card title="Evidence">
          <ul className="space-y-1">
            {explainItems.map((e) => (
              <li key={e.label} className="flex justify-between text-sm">
                <span className="text-osap-muted">{e.label}</span>
                <span>{e.value}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {tab === "relationships" ? (
        <Card title="Relationships">
          <div className="space-y-4">
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
        </Card>
      ) : null}

      {/* Candidate works */}
      {candidates.length > 1 ? (
        <Card title="Other compatible works">
          <ul className="space-y-1">
            {candidates.map((c) => (
              <li key={c.work.work_id} className="flex justify-between">
                <span>
                  <span className="text-osap-accent">{stars(c.score)}</span> {c.work.composer ?? ""} — {c.work.title}
                </span>
                <span className="text-xs text-osap-muted">{c.items.length} reps</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
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
