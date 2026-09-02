import { useState } from "react";
import { Button } from "../components/Button";
import { LoginForm } from "../components/LoginForm";
import { RegisterForm } from "../components/RegisterForm";
import { useOidcLogin } from "../components/useOidcLogin";
import { useI18n } from "../i18n/I18n";
import { useSupport } from "../support";

// Página pública "Apoya a OSAP": explica el proyecto y prepara el flujo de apoyo.
// Misma filosofía que la antigua "Apoya Chorus" (SupportPage, ahora obsoleta):
// no vende agresivamente, comunica un proyecto cultural + comunidad + transparencia,
// y no simula pagos ni crea datos de suscripción.
//
// Fronteras:
//  - Identidad (login/registro) → Auth (vía useOidcLogin + formularios Auth).
//  - Relación de apoyo (estado/CTA) → SupportGateway (useSupport). En el MVP se deriva de
//    Auth; cuando exista osap-support cambiará la implementación, no esta página.

export function SupportOsapPage() {
  const { t } = useI18n();
  const support = useSupport();
  const { start: startOidc, error: oidcError } = useOidcLogin();
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authOpen, setAuthOpen] = useState(false);

  const openLogin = () => {
    if (support.authenticated) return;
    void (async () => {
      const opened = await startOidc();
      if (!opened) setAuthOpen(true);
    })();
  };

  const startSupport = () => {
    // Preparado para la futura integración con el proveedor de Membership.
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Intro */}
      <section className="text-center">
        <h1 className="text-2xl font-semibold">{t("osapSupport.title")}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-osap-muted">{t("osapSupport.intro")}</p>
      </section>

      {/* Qué es OSAP */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.whatIsTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.whatIsBody")}</p>
      </section>

      {/* Por qué necesitamos apoyo */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.whyTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.whyIntro")}</p>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          <li className="flex items-center gap-2 text-sm">
            <span className="text-osap-accent">🖥️</span> {t("osapSupport.whyInfra")}
          </li>
          <li className="flex items-center gap-2 text-sm">
            <span className="text-osap-accent">🔧</span> {t("osapSupport.whyDev")}
          </li>
          <li className="flex items-center gap-2 text-sm">
            <span className="text-osap-accent">🩺</span> {t("osapSupport.whyMaint")}
          </li>
          <li className="flex items-center gap-2 text-sm">
            <span className="text-osap-accent">🔬</span> {t("osapSupport.whyResearch")}
          </li>
          <li className="flex items-center gap-2 text-sm sm:col-span-2">
            <span className="text-osap-accent">🕰️</span> {t("osapSupport.whyTime")}
          </li>
        </ul>
      </section>

      {/* Qué significa apoyar */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.meanTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.meanBody")}</p>
      </section>

      {/* Qué ocurrirá después */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.nextTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.nextBody")}</p>
      </section>

      {/* CTA: identificación */}
      <section className="rounded border border-osap-border bg-osap-surface p-6 text-center">
        {!support.authenticated ? (
          <>
            <Button onClick={openLogin}>{t("osapSupport.loginCta")}</Button>
            {oidcError && <p className="mt-2 text-xs text-red-500">{oidcError}</p>}
            {authOpen && (
              <div className="mx-auto mt-4 max-w-xs rounded border border-osap-border bg-osap-bg p-3 text-left shadow">
                <div className="mb-2 flex gap-2 text-sm">
                  <button
                    type="button"
                    onClick={() => setAuthMode("login")}
                    className={authMode === "login" ? "font-semibold text-osap-accent" : "text-osap-muted"}
                  >
                    {t("auth.login")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setAuthMode("register")}
                    className={authMode === "register" ? "font-semibold text-osap-accent" : "text-osap-muted"}
                  >
                    {t("auth.register")}
                  </button>
                </div>
                {authMode === "login" ? (
                  <LoginForm onDone={() => setAuthOpen(false)} />
                ) : (
                  <RegisterForm onDone={() => setAuthOpen(false)} />
                )}
              </div>
            )}
          </>
        ) : (
          <>
            <Button onClick={startSupport}>{t("osapSupport.startCta")}</Button>
            <p className="mt-3 text-sm text-osap-muted">{t("osapSupport.authenticatedInfo")}</p>
          </>
        )}
      </section>

      {/* Privacidad */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.privacyTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.privacyBody")}</p>
      </section>
    </div>
  );
}
