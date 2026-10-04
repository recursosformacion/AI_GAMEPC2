// Página pública "Colaboradores".
//
// 1) Reconocimiento real: lista pública (GET /api/v1/public/collaborators?project=omr),
//    una entrada por persona con sus badges. El backend ya agrupa y ordena: aquí no se
//    reordena ni se muestra granted_at.
// 2) Contenido informativo existente: formas de colaborar, significado de los
//    reconocimientos y nota de consentimiento.
//
// La SPA no conoce user_id ni habla con auth/support: solo con osap-api.

import { useEffect } from "react";
import { Link } from "react-router-dom";
import type { TKey } from "../i18n/translations";
import { Button } from "../components/Button";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useCollaborators } from "../state/collaborators";

// Alta de usuario: pantalla dedicada de osap-auth (misma que el flujo real del ecosistema).
const AUTH_REGISTER_URL = "https://auth.openmusicrepository.com/auth/register";

const WAYS = [
  {
    icon: "💚",
    titleKey: "collaborators.supportTitle",
    subKey: "collaborators.supportSub",
    ctaKey: "collaborators.supportCta",
    to: "/support",
    external: false,
  },
  {
    icon: "🤝",
    titleKey: "collaborators.contributeTitle",
    subKey: "collaborators.contributeSub",
    ctaKey: "collaborators.createAccountCta",
    to: AUTH_REGISTER_URL,
    external: true,
  },
  {
    icon: "📣",
    titleKey: "collaborators.shareTitle",
    subKey: "collaborators.shareSub",
    ctaKey: "collaborators.createAccountCta",
    to: AUTH_REGISTER_URL,
    external: true,
  },
  {
    icon: "🎼",
    titleKey: "collaborators.contentTitle",
    subKey: "collaborators.contentSub",
    ctaKey: "collaborators.createAccountCta",
    to: AUTH_REGISTER_URL,
    external: true,
  },
] as const;

const RECOGNITIONS = [
  { icon: "❤️", labelKey: "collaborators.recSupporter" },
  { icon: "🎼", labelKey: "collaborators.recContributor" },
  { icon: "📣", labelKey: "collaborators.recVoice" },
  { icon: "🏛️", labelKey: "collaborators.recFounder" },
] as const;

// Badges cortos por tipo de reconocimiento (los textos largos viven en la leyenda inferior).
const BADGES: Record<string, { icon: string; labelKey: TKey }> = {
  supporter: { icon: "❤️", labelKey: "collaborators.badgeSupporter" },
  contributor: { icon: "🎼", labelKey: "collaborators.badgeContributor" },
  voice: { icon: "📣", labelKey: "collaborators.badgeVoice" },
  founder: { icon: "🏛️", labelKey: "collaborators.badgeFounder" },
};

function Badge({ type }: { type: string }) {
  const { t } = useI18n();
  const meta = BADGES[type.toLowerCase()];
  if (!meta) {
    return null;
  }
  return (
    <span className="inline-flex items-center gap-1 rounded border border-osap-border px-2 py-0.5 text-xs">
      <span aria-hidden="true">{meta.icon}</span>
      {t(meta.labelKey)}
    </span>
  );
}

export function CollaboratorsPage() {
  const { t } = useI18n();
  const { data, loading, error, list } = useCollaborators();
  useEffect(() => {
    void list("omr");
  }, [list]);

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">{t("collaborators.title")}</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-osap-muted">{t("collaborators.idea")}</p>
      </div>

      <section>
        <h2 className="text-lg font-semibold">{t("collaborators.listTitle")}</h2>
        <div className="mt-4">
          <Envelope
            loading={loading}
            error={error}
            data={data}
            emptyMessage={t("collaborators.empty")}
          >
            {(people) => (
              <ul className="divide-y divide-osap-border rounded border border-osap-border bg-osap-surface">
                {people.map((person, index) => (
                  <li
                    key={`${person.nickname}-${index}`}
                    className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-2"
                  >
                    <span className="font-semibold">{person.nickname}</span>
                    <span className="flex flex-wrap items-center gap-2">
                      {person.recognitions.map((rec) => (
                        <Badge key={`${person.nickname}-${rec.type}`} type={rec.type} />
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Envelope>
        </div>
      </section>

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
                  {way.external ? (
                    <a href={way.to}>
                      <Button>{t(way.ctaKey)}</Button>
                    </a>
                  ) : (
                    <Link to={way.to}>
                      <Button>{t(way.ctaKey)}</Button>
                    </Link>
                  )}
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
