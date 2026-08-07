import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import { ResultList } from "../components/ResultList";
import { useI18n } from "../i18n/I18n";
import { useSessionSources } from "../state/sources";

const SOURCE_TYPES = ["Local", "Git", "HTTP", "WebDAV", "FTP", "OPDS"];

export function SourcesPage() {
  const { t } = useI18n();
  const { list, listAll, create, analyze, use: useSource, forget } = useSessionSources();
  const [name, setName] = useState("");
  const [type, setType] = useState("Local");
  const [location, setLocation] = useState("");

  useEffect(() => {
    void listAll();
  }, [listAll]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    void create({ name, type, location });
    setName("");
    setLocation("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("nav.sources")}</h1>

      <Card title="Add a source (use it immediately)">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col text-sm">
            Name
            <input aria-label="name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1 rounded border border-osap-border px-2 py-1" />
          </label>
          <label className="flex flex-col text-sm">
            Type
            <select aria-label="type" value={type} onChange={(e) => setType(e.target.value)} className="mt-1 rounded border border-osap-border px-2 py-1">
              {SOURCE_TYPES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            Location / URL
            <input aria-label="location" value={location} onChange={(e) => setLocation(e.target.value)} className="mt-1 rounded border border-osap-border px-2 py-1" />
          </label>
          <Button type="submit">Add</Button>
        </form>
      </Card>

      <Card title="Your session sources">
        <Envelope loading={list.loading} error={list.error} data={list.data} emptyMessage="No session sources yet">
          {(sources) => (
            <ResultList
              items={sources}
              keyOf={(s) => s.source_id}
              renderItem={(s) => (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">{s.name}</span>
                    <span className="ml-2 text-xs text-osap-muted">
                      {s.type} · {s.status}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <Button onClick={() => void analyze(s.source_id)}>Analyze</Button>
                    <Button onClick={() => void useSource(s.source_id)}>Use</Button>
                    <Button onClick={() => void forget(s.source_id)}>Forget</Button>
                  </div>
                </div>
              )}
            />
          )}
        </Envelope>
      </Card>
    </div>
  );
}
