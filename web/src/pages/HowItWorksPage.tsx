// Página "Cómo funciona OSAP" — guía concisa y honesta (i18n, 5 idiomas).
//
// Editorial v1: separa claramente lo que ya funciona, lo que es funcionamiento actual y
// lo que realmente es futuro. Sin inventar capacidades. CTA final → Colaboradores.

import { Link } from "react-router-dom";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/I18n";

export function HowItWorksPage() {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">{t("how.title")}</h1>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-osap-muted">{t("how.intro")}</p>
      </div>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">{t("how.whatTitle")}</h2>
        <p className="text-sm">{t("how.whatBody1")}</p>
        <p className="mt-2 text-sm text-osap-muted">{t("how.whatBody2")}</p>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">{t("how.worksTitle")}</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>{t("how.worksBullet1")}</li>
          <li>{t("how.worksBullet2")}</li>
          <li>{t("how.worksBullet3")}</li>
          <li>{t("how.worksBullet4")}</li>
        </ul>
      </section>

      <section id="downloads" className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">{t("how.accessTitle")}</h2>
        <p className="text-sm">{t("how.accessFree")}</p>
        <p className="mt-2 text-sm text-osap-muted">{t("how.accessDownloads")}</p>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">{t("how.futureTitle")}</h2>
        <p className="text-sm text-osap-muted">{t("how.futureBody")}</p>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">{t("how.startTitle")}</h2>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>{t("how.start1")}</li>
          <li>{t("how.start2")}</li>
          <li>{t("how.start3")}</li>
          <li>{t("how.start4")}</li>
        </ol>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-6 text-center">
        <h2 className="text-lg font-semibold">{t("how.joinTitle")}</h2>
        <p className="mx-auto mt-1 max-w-xl text-sm text-osap-muted">{t("how.joinBody")}</p>
        <div className="mt-4">
          <Link to="/collaborators">
            <Button>{t("how.joinCta")}</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
