import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useI18n } from "../i18n/I18n";
import { searchAndGo } from "../state/navigation";

function hint(query: string): string | null {
  const q = query.trim();
  if (/^(kv|k\.?|bwv|op\.?|hob\.?)\s?[0-9]/i.test(q)) return "Looks like a catalogue number — search as catalogue.";
  if (/mozart|bach|beethoven|byrd|poulenc/i.test(q)) return "Looks like a composer — you can also use Advanced search.";
  return null;
}

export function HomePage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [composer, setComposer] = useState("");
  const [title, setTitle] = useState("");
  const [catalogue, setCatalogue] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const payload = {
      query,
      limit: 50,
      composer: composer || null,
      title: title || null,
      catalogue: catalogue || null,
    };
    if (!query.trim() && !composer && !title && !catalogue) return;
    void searchAndGo(navigate, payload);
  };

  return (
    <div className="space-y-6">
      <section className="py-10 text-center">
        <h1 className="text-2xl font-bold text-osap-accent sm:text-3xl">{t("app.name")}</h1>
        <p className="text-sm text-osap-muted">{t("app.subtitle")}</p>
        <p className="mx-auto mt-2 max-w-xl text-osap-muted">{t("tagline")}</p>

        <form onSubmit={submit} className="mx-auto mt-6 max-w-xl">
          <div className="flex gap-2">
            <input
              aria-label="home-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("search.placeholder")}
              className="flex-1 rounded border border-osap-border bg-osap-surface px-3 py-2"
            />
            <Button type="submit">{t("search")}</Button>
          </div>
          {hint(query) ? <p className="mt-1 text-left text-xs text-osap-muted">💡 {hint(query)}</p> : null}

          <button type="button" onClick={() => setAdvanced((v) => !v)} className="mt-2 text-xs text-osap-accent">
            {advanced ? "− Advanced" : "+ Advanced"}
          </button>

          {advanced ? (
            <div className="mt-2 grid grid-cols-2 gap-2 text-left">
              <label className="flex flex-col text-xs">
                Composer
                <input aria-label="composer" value={composer} onChange={(e) => setComposer(e.target.value)} className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1" />
              </label>
              <label className="flex flex-col text-xs">
                Title
                <input aria-label="title" value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1" />
              </label>
              <label className="flex flex-col text-xs">
                Catalogue
                <input aria-label="catalogue" value={catalogue} onChange={(e) => setCatalogue(e.target.value)} className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1" />
              </label>
            </div>
          ) : null}
        </form>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card title={t("home.recent")}>
          <EmptyState />
        </Card>
        <Card title={t("home.mostAccessed")}>
          <EmptyState />
        </Card>
        <Card title={t("home.recentlyAdded")}>
          <EmptyState />
        </Card>
        <Card title={t("home.repositoryStatus")}>
          <EmptyState />
        </Card>
      </div>
    </div>
  );
}
