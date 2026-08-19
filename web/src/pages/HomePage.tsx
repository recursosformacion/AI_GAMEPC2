import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";
import { searchAndGo } from "../state/navigation";
import { useSources } from "../state/repositorySources";

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
  const { list, loadList } = useSources();

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const payload = {
      query,
      limit: 30,
      composer: composer || null,
      title: title || null,
      catalogue: catalogue || null,
    };
    if (!query.trim() && !composer && !title && !catalogue) return;
    void searchAndGo(navigate, payload);
  };

  const wiredSources = (list.data ?? []).filter((s) => s.status === "Online").slice(0, 6);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="py-8 text-center">
        <h1 className="mx-auto max-w-2xl text-2xl font-bold text-osap-ink sm:text-3xl">
          {t("home.headline")}
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-osap-muted">{t("home.subtitle")}</p>

        {/* Qué encontrarás */}
        <div className="mx-auto mt-6 grid max-w-3xl gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded border border-osap-border bg-osap-surface p-3 text-center">
            <div className="text-2xl">🎼</div>
            <h3 className="mt-1 font-semibold text-osap-ink">MusicXML</h3>
            <p className="mt-1 text-xs text-osap-muted">{t("home.formatMusicxml")}</p>
          </div>
          <div className="rounded border border-osap-border bg-osap-surface p-3 text-center">
            <div className="text-2xl">📄</div>
            <h3 className="mt-1 font-semibold text-osap-ink">PDF</h3>
            <p className="mt-1 text-xs text-osap-muted">{t("home.formatPdf")}</p>
          </div>
          <div className="rounded border border-osap-border bg-osap-surface p-3 text-center">
            <div className="text-2xl">🎵</div>
            <h3 className="mt-1 font-semibold text-osap-ink">MIDI</h3>
            <p className="mt-1 text-xs text-osap-muted">{t("home.formatMidi")}</p>
          </div>
          <div className="rounded border border-osap-border bg-osap-surface p-3 text-center">
            <div className="text-2xl">💰</div>
            <h3 className="mt-1 font-semibold text-osap-ink">{t("home.formatPaid")}</h3>
            <p className="mt-1 text-xs text-osap-muted">{t("home.formatPaidDesc")}</p>
          </div>
        </div>

        <p className="mx-auto mt-7 max-w-xl font-medium text-osap-ink">{t("home.cta")}</p>

        <form onSubmit={submit} className="mx-auto mt-3 max-w-xl">
          <div className="flex gap-2">
            <input
              aria-label="home-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("home.searchPlaceholder")}
              className="flex-1 rounded border border-osap-border bg-osap-surface px-3 py-2"
            />
            <Button type="submit">{t("search")}</Button>
          </div>
          {hint(query) ? <p className="mt-1 text-left text-xs text-osap-muted">💡 {hint(query)}</p> : null}

          <button type="button" onClick={() => setAdvanced((v) => !v)} className="mt-2 text-xs text-osap-accent">
            {advanced ? t("home.advancedMinus") : t("home.advanced")}
          </button>

          {advanced ? (
            <div className="mt-2 grid grid-cols-2 gap-2 text-left">
              <label className="flex flex-col text-xs">
                {t("home.composer")}
                <input aria-label="composer" value={composer} onChange={(e) => setComposer(e.target.value)} className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1" />
              </label>
              <label className="flex flex-col text-xs">
                {t("home.title")}
                <input aria-label="title" value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1" />
              </label>
              <label className="flex flex-col text-xs">
                {t("home.catalogue")}
                <input aria-label="catalogue" value={catalogue} onChange={(e) => setCatalogue(e.target.value)} className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1" />
              </label>
            </div>
          ) : null}
        </form>
      </section>

      {/* ¿Cómo funciona OSAP? */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-center text-lg font-semibold">{t("home.whatIsTitle")}</h2>
        <p className="mx-auto mt-1 max-w-2xl text-center text-sm text-osap-muted">{t("home.notRepo")}</p>

        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <div className="text-center">
            <div className="text-2xl">🔎</div>
            <h3 className="mt-1 font-semibold uppercase tracking-wide text-osap-accent">{t("home.discover")}</h3>
            <p className="mt-1 text-sm text-osap-muted">{t("home.discoverDesc")}</p>
          </div>
          <div className="text-center">
            <div className="text-2xl">🎼</div>
            <h3 className="mt-1 font-semibold uppercase tracking-wide text-osap-accent">{t("home.understand")}</h3>
            <p className="mt-1 text-sm text-osap-muted">{t("home.understandDesc")}</p>
          </div>
          <div className="text-center">
            <div className="text-2xl">🔗</div>
            <h3 className="mt-1 font-semibold uppercase tracking-wide text-osap-accent">{t("home.access")}</h3>
            <p className="mt-1 text-sm text-osap-muted">{t("home.accessDesc")}</p>
          </div>
        </div>

        <div className="mt-4 text-center">
          <Link to="/about/how-it-works" className="text-sm font-medium text-osap-accent hover:underline">
            {t("home.howItWorks")}
          </Link>
        </div>
      </section>

      {/* Explorar */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card title={t("home.recent")}>
          <p className="text-sm text-osap-muted">{t("home.recentEmpty")}</p>
        </Card>
        <Card title={t("home.mostAccessed")}>
          <p className="text-sm text-osap-muted">{t("home.mostAccessedEmpty")}</p>
        </Card>
        <Card title={t("home.recentlyAdded")}>
          <p className="text-sm text-osap-muted">{t("home.recentlyAddedEmpty")}</p>
        </Card>
        <Card title={t("home.sourcesAvailable")}>
          {wiredSources.length === 0 ? (
            <p className="text-sm text-osap-muted">{t("home.sourcesEmpty")}</p>
          ) : (
            <ul className="space-y-1">
              {wiredSources.map((s) => (
                <li key={s.source_id} className="flex items-center gap-2 text-sm">
                  <span className="text-green-600">✓</span>
                  <span className="truncate">{s.name}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
