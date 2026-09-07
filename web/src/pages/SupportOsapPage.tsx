import { useState } from "react";
import { Button } from "../components/Button";
import { LoginForm } from "../components/LoginForm";
import { RegisterForm } from "../components/RegisterForm";
import { useOidcLogin } from "../components/useOidcLogin";
import { useI18n } from "../i18n/I18n";
import { startDonation, startMembership, useSupport } from "../support";
import { useAuth } from "../state/auth";

// Página "Apoya a OSAP": explica el proyecto y ofrece el flujo de apoyo REAL contra
// osap-support (PayPal). No simula pagos: el botón abre el checkout real de PayPal y el
// estado mostrado es el que confirma osap-support (/membership/me).
//
// Fronteras:
//  - Identidad (login/registro) → Auth (vía useOidcLogin + formularios Auth).
//  - Relación de apoyo (estado/CTA) → useSupport (osap-support HTTP).

const DONATION_PRESET_MINOR = 500; // 5,00 EUR (centavos) — importe real validado en backend
const RETURN_URL = typeof window === "undefined" ? "/support" : `${window.location.origin}/support`;

// Estados no activos de membership que el backend confirma (frontend NO decide);
// solo se traducen a i18n los valores que osap-support ya respondió en /membership/me.

const SUPPORTER_PLANS = [
  {
    periodicity: "monthly",
    titleKey: "osapSupport.planMonthly",
    priceKey: "osapSupport.planMonthlyPrice",
    ctaKey: "osapSupport.joinMonthly",
  },
  {
    periodicity: "yearly",
    titleKey: "osapSupport.planYearly",
    priceKey: "osapSupport.planYearlyPrice",
    ctaKey: "osapSupport.joinYearly",
  },
] as const;

export function SupportOsapPage() {
  const { t } = useI18n();
  const support = useSupport();
  const accessToken = useAuth((s) => s.accessToken);
  const { start: startOidc, error: oidcError } = useOidcLogin();
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authOpen, setAuthOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [membershipStarting, setMembershipStarting] = useState<string | null>(null);
  const [membershipError, setMembershipError] = useState<string | null>(null);

  const openLogin = () => {
    if (support.authenticated) return;
    void (async () => {
      const opened = await startOidc();
      if (!opened) setAuthOpen(true);
    })();
  };

  const startSupport = () => {
    // Donación puntual real: osap-support → PayPal. Nunca se marca pago localmente.
    if (!accessToken) {
      openLogin();
      return;
    }
    setStarting(true);
    setActionError(null);
    void (async () => {
      try {
        const checkout = await startDonation(
          accessToken,
          DONATION_PRESET_MINOR,
          "EUR",
          RETURN_URL,
        );
        window.location.assign(checkout.checkout_url);
      } catch (error) {
        setActionError(error instanceof Error ? error.message : "support unavailable");
        setStarting(false);
      }
    })();
  };

  const startMembershipPlan = (periodicity: "monthly" | "yearly") => {
    // Membresía real: osap-support → PayPal. Sin token no se intenta el checkout.
    if (!accessToken) {
      openLogin();
      return;
    }
    setMembershipStarting(periodicity);
    setMembershipError(null);
    void (async () => {
      try {
        const checkout = await startMembership(accessToken, "supporter", periodicity, RETURN_URL);
        window.location.assign(checkout.checkout_url);
      } catch (error) {
        setMembershipError(error instanceof Error ? error.message : "support unavailable");
        setMembershipStarting(null);
      }
    })();
  };

  const membershipView = support.membership;
  const activeSupporter = membershipView?.status === "active";
  const membershipStatus = membershipView?.status;
  const statusText =
    membershipStatus === "pending"
      ? t("osapSupport.statePending")
      : membershipStatus === "past_due"
        ? t("osapSupport.statePastDue")
        : membershipStatus === "cancelled"
          ? t("osapSupport.stateCancelled")
          : membershipStatus === "expired"
            ? t("osapSupport.stateExpired")
            : null;

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

      {/* Membresía Supporter (backend real /membership/me + checkout) */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.membershipTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.membershipIntro")}</p>

        {!support.authenticated ? (
          <div className="mt-4 text-center">
            <p className="text-sm text-osap-muted">{t("osapSupport.loginToJoin")}</p>
            <div className="mt-3">
              <Button onClick={openLogin}>{t("auth.login")}</Button>
            </div>
          </div>
        ) : support.status === "loading" ? (
          <p className="mt-4 text-sm text-osap-muted">…</p>
        ) : support.status === "unavailable" ? null : activeSupporter ? (
          <div className="mt-4 text-center">
            <p className="text-sm font-medium text-osap-accent">{t("osapSupport.activeMember")}</p>
            <p className="mt-1 text-sm text-osap-muted">
              {membershipView?.periodicity === "yearly"
                ? t("osapSupport.planYearly")
                : t("osapSupport.planMonthly")}
            </p>
          </div>
        ) : statusText ? (
          <p className="mt-4 text-sm text-osap-muted">{statusText}</p>
        ) : (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {SUPPORTER_PLANS.map((plan) => (
                <div
                  key={plan.periodicity}
                  className="rounded border border-osap-border bg-osap-bg p-4 text-center"
                >
                  <p className="text-sm font-semibold">{t(plan.titleKey)}</p>
                  <p className="mt-1 text-sm text-osap-muted">{t(plan.priceKey)}</p>
                  <div className="mt-3">
                    <Button
                      onClick={() => startMembershipPlan(plan.periodicity)}
                      disabled={membershipStarting !== null}
                    >
                      {membershipStarting === plan.periodicity ? "…" : t(plan.ctaKey)}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            {membershipError && (
              <p className="mt-3 text-xs text-red-500">{membershipError}</p>
            )}
          </>
        )}
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
        ) : support.status === "loading" ? (
          <p className="text-sm text-osap-muted">…</p>
        ) : support.status === "member" ? (
          <>
            <p className="text-sm font-medium text-osap-accent">{t("osapSupport.memberStatus")}</p>
            <p className="mt-1 text-sm text-osap-muted">
              {support.membership?.level ?? ""} · {support.membership?.status ?? ""}
            </p>
          </>
        ) : support.status === "no_membership" ? (
          <>
            <p className="text-sm text-osap-muted">{t("osapSupport.noMember")}</p>
            <Button onClick={startSupport} disabled={starting}>
              {starting ? "…" : t("osapSupport.donateCta")}
            </Button>
            {actionError && <p className="mt-2 text-xs text-red-500">{actionError}</p>}
          </>
        ) : (
          <>
            <p className="text-sm text-osap-muted">{t("osapSupport.membershipUnavailable")}</p>
            {actionError && <p className="mt-2 text-xs text-red-500">{actionError}</p>}
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
