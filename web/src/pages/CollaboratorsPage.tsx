// Página pública "Colaboradores": puente entre "Cómo funciona" y "Apoyar".
//
// NO explica el funcionamiento interno de OSAP (eso vive en /about/how-it-works).
// Muestra que participar no significa solo aportar dinero: cuatro formas de colaborar y
// el significado de los reconocimientos (Supporter/Contributor/Voice/Founder), con la
// nota de consentimiento para los reconocimientos públicos.

import { Link } from "react-router-dom";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/I18n";

const WAYS = [
  {
    icon: "💚",
    titleKey: "collaborators.supportTitle",
    subKey: "collaborators.supportSub",
    ctaKey: "collaborators.supportCta",
    to: "/support",
  },
  {
    icon: "🤝",
    titleKey: "collaborators.contributeTitle",
    subKey: "collaborators.contributeSub",
    ctaKey: "collaborators.createAccountCta",
    to: "/support?mode=register",
  },
  {
    icon: "📣",
    titleKey: "collaborators.shareTitle",
    subKey: "collaborators.shareSub",
    ctaKey: "collaborators.createAccountCta",
    to: "/support?mode=register",
  },
  {
    icon: "🎼",
    titleKey: "collaborators.contentTitle",
    subKey: "collaborators.contentSub",
    ctaKey: "collaborators.createAccountCta",
    to: "/support?mode=register",
  },
] as const;

const RECOGNITIONS = [
  { icon: "❤️", labelKey: "collaborators.recSupporter" },
  { icon: "🎼", labelKey: "collaborators.recContributor" },
  { icon: "📣", labelKey: "collaborators.recVoice" },
  { icon: "🏛️", labelKey: "collaborators.recFounder" },
] as const;

export function CollaboratorsPage() {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">{t("collaborators.title")}</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-osap-muted">{t("collaborators.idea")}</p>
      </div>

      <section>
        <h2 className="text-lg font-semibold">{t("collaborators.joinTitle")}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {WAYS.map((way) => (
            <div key={way.titleKey} className="rounded border border-osap-border bg-osap-surface p-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{way.icon}</span>
                <h3 className="font-semibold">{t(way.titleKey)}</h3>
              </div>
              <p className="mt-1 text-sm text-osap-muted">{t(way.subKey)}</p>
              {"ctaKey" in way && way.to ? (
                <div className="mt-3">
                  <Link to={way.to}>
                    <Button>{t(way.ctaKey)}</Button>
                  </Link>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("collaborators.recognitionsTitle")}</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {RECOGNITIONS.map((rec) => (
            <li key={rec.labelKey}>
              <span className="mr-2">{rec.icon}</span>
              {t(rec.labelKey)}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-osap-muted">{t("collaborators.consent")}</p>
      </section>
    </div>
  );
}
