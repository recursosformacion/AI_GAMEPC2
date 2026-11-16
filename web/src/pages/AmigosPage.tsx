import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { chorusBaseUrl, chorusSessionUrl } from "../lib/chorus";

// «Los amigos»: entrada de la sección. Presenta las subsecciones (hoy «Corales») y el
// espacio personal del usuario autenticado (mis artículos). No lista artículos aquí: los
// artículos viven dentro de la página de cada grupo.
export function AmigosPage() {
  const { t } = useI18n();
  const user = useAuth((s) => s.user);
  const isAdmin = useAuth((s) => s.isAdmin());
  const token = useAuth((s) => s.accessToken);
  const refreshToken = useAuth((s) => s.refreshToken);

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("nav.sectionFriends")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("nav.friends")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("friends.subtitle")}</p>
        <a
          href={`${chorusBaseUrl()}/alta.html`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block text-sm font-medium text-osap-accent hover:underline"
        >
          Solicitar alta de grupo o entidad →
        </a>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card title={t("friends.coralesTitle")}>
          <p className="text-sm text-osap-muted">{t("friends.coralesSubtitle")}</p>
          <Link
            to="/amigos/corales"
            className="mt-3 inline-block rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white hover:bg-osap-accent/90"
          >
            {t("friends.coralesTitle")} →
          </Link>
        </Card>

        <Card title={t("friends.chorusTitle")}>
          <p className="text-sm text-osap-muted">{t("friends.chorusSubtitle")}</p>
          <a
            href={chorusSessionUrl(token, refreshToken)}
            target="_blank"
            rel="noopener noreferrer"
            referrerPolicy="no-referrer"
            className="mt-3 inline-block rounded-md border border-osap-accent px-4 py-2 text-sm font-medium text-osap-accent hover:bg-osap-accent-soft"
          >
            {t("friends.openChorus")} →
          </a>
        </Card>

        {user !== null ? (
          <Card title={t("nav.myArticles")}>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/amigos/mis-articulos"
                className="rounded-md border border-osap-border px-3 py-1.5 text-sm hover:border-osap-accent hover:text-osap-accent"
              >
                {t("nav.myArticles")}
              </Link>
              <Link
                to="/amigos/editor"
                className="rounded-md bg-osap-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-osap-accent/90"
              >
                {t("friends.newArticle")}
              </Link>
            </div>
          </Card>
        ) : (
          <Card title={t("nav.myArticles")}>
            <p className="text-sm text-osap-muted">{t("friends.loginToWrite")}</p>
          </Card>
        )}
      </div>

      {isAdmin ? (
        <p>
          <Link to="/admin/amigos" className="text-sm text-osap-accent hover:underline">
            {t("friends.adminGroups")} ({t("admin.title")}) →
          </Link>
        </p>
      ) : null}
    </div>
  );
}



