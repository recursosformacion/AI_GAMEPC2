import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../api/ApiClient";
import type { AmigosArticle, AmigosGroup } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";

export function AmigosGroupDetailPage() {
  const { groupId } = useParams();
  const { t } = useI18n();
  const [group, setGroup] = useState<AmigosGroup | null>(null);
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!groupId) return;
    setLoading(true);
    Promise.all([
      apiClient.getAmigosGroups(),
      apiClient.getAmigosGroupArticles(groupId).catch(() => ({ items: [], total: 0 })),
    ])
      .then(([groups, list]) => {
        if (cancelled) return;
        const found = groups.find((item) => item.id === groupId) ?? null;
        setGroup(found);
        setArticles(list.items);
        if (!found) setError(t("friends.groupsEmpty"));
      })
      .catch(() => {
        if (!cancelled) setError(t("friends.groupsEmpty"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [groupId, t]);

  if (loading) return <Spinner label={t("states.loading")} />;
  if (!group) return <p className="text-sm text-osap-muted">{error ?? t("friends.groupsEmpty")}</p>;

  const kindLabel =
    ({ coral: "Coral", grupo: "Grupo", banda: "Banda", orquesta: "Orquesta",
       ensemble: "Ensemble", escuela: "Escuela", iglesia: "Iglesia" })[group.kind] ?? group.kind;

  return (
    <div className="space-y-6">
      <nav className="text-xs text-osap-muted">
        <Link to="/" className="hover:text-osap-accent">Inicio</Link> ›{" "}
        <Link to="/amigos" className="hover:text-osap-accent">Los amigos</Link> ›{" "}
        <Link to="/amigos/grupos" className="hover:text-osap-accent">Grupos</Link> ›{" "}
        <span>{group.name}</span>
      </nav>

      <header className="flex flex-wrap items-start gap-4 border-b border-osap-border pb-5">
        {group.image_url || group.logo_url ? (
          <img
            src={group.logo_url ?? group.image_url ?? ""}
            alt=""
            className="h-20 w-20 rounded-md object-cover"
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
            {kindLabel}
          </p>
          <h1 className="mt-1 text-3xl font-semibold text-osap-ink">{group.name}</h1>
          {group.description ? (
            <p className="mt-2 max-w-3xl text-sm text-osap-muted">{group.description}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded bg-osap-accent-soft px-2 py-1 text-osap-accent">{kindLabel}</span>
            {group.website ? (
              <a
                href={group.website}
                target="_blank"
                rel="nofollow noopener noreferrer"
                className="rounded border border-osap-border px-2 py-1 text-osap-accent"
              >
                Web
              </a>
            ) : null}
            {group.email ? (
              <a
                href={`mailto:${group.email}`}
                className="rounded border border-osap-border px-2 py-1 text-osap-accent"
              >
                Email
              </a>
            ) : null}
          </div>
        </div>
      </header>

      {group.technical_description ? (
        <section className="rounded-card border border-osap-border bg-osap-surface p-4">
          <h2 className="text-lg font-semibold text-osap-ink">Descripción técnica</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm text-osap-ink">{group.technical_description}</p>
        </section>
      ) : null}

      <section className="rounded-card border border-osap-border bg-osap-surface p-4">
        <h2 className="text-lg font-semibold text-osap-ink">Cargos</h2>
        <p className="mt-2 text-sm text-osap-ink">
          <strong>Administrativos:</strong> {group.admin_roles?.join(", ") || "—"}
        </p>
        <p className="mt-1 text-sm text-osap-ink">
          <strong>Musicales:</strong> {group.musical_roles?.join(", ") || "—"}
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-osap-ink">Publicaciones</h2>
        {articles.length === 0 ? (
          <p className="mt-2 text-sm text-osap-muted">Todavía no hay publicaciones de este grupo.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {articles.map((article) => (
              <li key={article.id}>
                <Link
                  to={`/amigos/articulo/${encodeURIComponent(article.id)}/${article.slug}`}
                  className="font-medium text-osap-accent hover:underline"
                >
                  {article.title}
                </Link>
                <span className="ml-2 text-xs text-osap-muted">{article.event_date}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

