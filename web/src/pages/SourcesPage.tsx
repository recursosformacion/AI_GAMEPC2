import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { useSources } from "../state/repositorySources";

const SOURCE_TYPES = ["Local", "Git", "HTTP", "WebDAV", "FTP", "OPDS"];
type Step = "form" | "mapping" | "done";

export function SourcesPage() {
  const { t } = useI18n();
  const isLoggedIn = useAuth((s) => s.isAuthenticated());
  const { list, loadList } = useSources();

  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("form");
  const [name, setName] = useState("");
  const [type, setType] = useState("HTTP");
  const [url, setUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [fields, setFields] = useState<string[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const startAdd = () => {
    setOpen(true);
    setStep("form");
    setName("");
    setType("HTTP");
    setUrl("");
    setFields([]);
    setLabels({});
    setPreviewError(null);
    setSuggestion(null);
    setSubmitError(null);
  };

  const check = async () => {
    if (!url.trim()) return;
    setChecking(true);
    setPreviewError(null);
    try {
      const preview = await apiClient.previewSource(url.trim());
      if (!preview.ok) {
        setPreviewError(preview.error ?? t("sources.previewFailed"));
        setFields([]);
      } else {
        setFields(preview.fields);
        setLabels(Object.fromEntries(preview.fields.map((f) => [f, f])));
        setStep("mapping");
      }
    } catch {
      setPreviewError(t("sources.previewFailed"));
    } finally {
      setChecking(false);
    }
  };

  const suggest = async () => {
    if (!isLoggedIn) {
      setSubmitError(t("sources.loginToSuggest"));
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await apiClient.suggestSource({
        name: name.trim(),
        type,
        location: url.trim(),
        mapping: { ...labels },
      });
      setSuggestion(result.id);
      setStep("done");
    } catch {
      setSubmitError(t("sources.suggestFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("nav.sources")}</h1>
        <Button onClick={startAdd}>{t("sources.add")}</Button>
      </div>

      {open && (
        <Card title={t("sources.addTitle")}>
          {step === "form" && (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="flex flex-col text-sm">
                  {t("sources.name")}
                  <input aria-label="name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1 rounded border border-osap-border px-2 py-1" />
                </label>
                <label className="flex flex-col text-sm">
                  {t("sources.type")}
                  <select aria-label="type" value={type} onChange={(e) => setType(e.target.value)} className="mt-1 rounded border border-osap-border px-2 py-1">
                    {SOURCE_TYPES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="flex flex-col text-sm">
                {t("sources.connection")}
                <input
                  aria-label="location"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://... / manifest.json / path"
                  className="mt-1 rounded border border-osap-border px-2 py-1"
                />
              </label>
              {previewError && <p className="text-sm text-red-600">{previewError}</p>}
              <div className="flex gap-2">
                <Button onClick={check} disabled={checking || !url.trim()}>
                  {checking ? t("states.loading") : t("sources.check")}
                </Button>
                <Button className="bg-transparent text-osap-ink hover:bg-osap-accent-soft" onClick={() => setOpen(false)}>
                  {t("sources.cancel")}
                </Button>
              </div>
            </div>
          )}

          {step === "mapping" && (
            <div className="space-y-3">
              <p className="text-sm text-osap-muted">{t("sources.mappingHint")}</p>
              {fields.map((f) => (
                <label key={f} className="flex items-center gap-2 text-sm">
                  <code className="w-48 truncate text-osap-muted">{f}</code>
                  <span>→</span>
                  <input
                    value={labels[f] ?? f}
                    onChange={(e) => setLabels({ ...labels, [f]: e.target.value })}
                    className="flex-1 rounded border border-osap-border px-2 py-1"
                  />
                </label>
              ))}
              <p className="text-xs text-osap-muted">{t("sources.mapToHint")}</p>
              {submitError && <p className="text-sm text-red-600">{submitError}</p>}
              <div className="flex gap-2">
                <Button onClick={suggest} disabled={submitting || !isLoggedIn}>
                  {submitting ? t("states.loading") : t("sources.suggest")}
                </Button>
                <Button className="bg-transparent text-osap-ink hover:bg-osap-accent-soft" onClick={() => setOpen(false)}>
                  {t("sources.cancel")}
                </Button>
              </div>
            </div>
          )}

          {step === "done" && (
            <div className="space-y-2">
              <p className="text-sm">{t("sources.suggestedDone")}</p>
              {suggestion && <p className="text-xs text-osap-muted">#{suggestion}</p>}
              <Button className="bg-transparent text-osap-ink hover:bg-osap-accent-soft" onClick={() => setOpen(false)}>
                {t("sources.close")}
              </Button>
            </div>
          )}
        </Card>
      )}

      <Card title={t("discover.wiredSources")}>
        <Envelope loading={list.loading} error={list.error} data={list.data} emptyMessage={t("discover.noCollections")}>
          {(sources) => {
            const wired = sources.filter((s) => s.status === "Online");
            if (wired.length === 0) return <p className="text-sm text-osap-muted">{t("discover.noCollections")}</p>;
            return (
              <ul className="divide-y divide-osap-border">
                {wired.map((s) => (
                  <li key={s.source_id} className="flex items-center justify-between py-2">
                    <span className="font-medium">{s.name}</span>
                    <span className="text-xs text-osap-muted">
                      {s.type} · {s.origin} · {s.trust}
                    </span>
                  </li>
                ))}
              </ul>
            );
          }}
        </Envelope>
      </Card>

      {checking && <Spinner />}
    </div>
  );
}
