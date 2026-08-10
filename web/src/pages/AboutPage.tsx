import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18n";

// Página "About" — índice de OSAP: qué es y enlace a "Cómo funciona OSAP".
export function AboutPage() {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">{t("about.title")}</h1>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">{t("about.whatIsTitle")}</h2>
        <p className="text-sm">{t("about.whatIsBody")}</p>
      </section>

      <nav className="grid gap-3 sm:grid-cols-2">
        <Link
          to="/about/how-it-works"
          className="rounded border border-osap-border bg-osap-surface p-4 hover:bg-osap-bg"
        >
          <h2 className="text-base font-semibold">{t("about.howItWorks")}</h2>
          <p className="mt-1 text-sm text-osap-muted">{t("about.howItWorksDesc")}</p>
        </Link>
        <Link
          to="/composers"
          className="rounded border border-osap-border bg-osap-surface p-4 hover:bg-osap-bg"
        >
          <h2 className="text-base font-semibold">{t("about.composers")}</h2>
          <p className="mt-1 text-sm text-osap-muted">{t("about.composersDesc")}</p>
        </Link>
      </nav>
    </div>
  );
}
