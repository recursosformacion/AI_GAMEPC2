// Página "Apoyar a OSAP" — composición de conversión v1 (Inspirar → Elegir → Resolver).
//
// Estructura: Hero (una frase) → ¿Cómo quieres ayudar? (Donación | Supporter, visibles
// también para anónimo) → ¿Por qué necesitamos apoyo? → Tu cuenta es tu relación con OSAP
// → Privacidad. La cuenta se pide SOLO al elegir una acción, con el flujo exacto elegido
// guardado (donation/one_time | membership/supporter/monthly|yearly).

import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { LoginForm } from "../components/LoginForm";
import { RegisterForm } from "../components/RegisterForm";
import { useOidcLogin } from "../components/useOidcLogin";
import { useI18n } from "../i18n/I18n";
import { startDonation, startMembership, useSupport } from "../support";
import {
  clearSupportIntent,
  intentMembershipPeriodicity,
  readSupportIntent,
  storeSupportIntent,
} from "../support/supportIntent";
import { useAuth } from "../state/auth";

const RETURN_URL = typeof window === "undefined" ? "/support" : `${window.location.origin}/support`;

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
  const [donationAmount, setDonationAmount] = useState("5");
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

  const parseDonationMinor = (): number | null => {
    const value = parseFloat(donationAmount.replace(",", "."));
    if (!Number.isFinite(value) || value <= 0) return null;
    return Math.round(value * 100);
  };

  const runDonation = async () => {
    if (!accessToken) return;
    const minor = parseDonationMinor();
    if (minor === null) {
      setActionError("amount invalid");
      return;
    }
    setStarting(true);
    setActionError(null);
    try {
      const checkout = await startDonation(accessToken, minor, "EUR", RETURN_URL);
      window.location.assign(checkout.checkout_url);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "support unavailable");
      setStarting(false);
    }
  };

  const runMembership = async (periodicity: "monthly" | "yearly") => {
    if (!accessToken) return;
    setMembershipStarting(periodicity);
    setMembershipError(null);
    try {
      const checkout = await startMembership(accessToken, "supporter", periodicity, RETURN_URL);
      window.location.assign(checkout.checkout_url);
    } catch (error) {
      setMembershipError(error instanceof Error ? error.message : "support unavailable");
      setMembershipStarting(null);
    }
  };

  // Intención persistida: si el anónimo eligió antes de autenticarse, al ganar token se
  // reanuda el flujo EXACTO (membership/supporter/monthly|yearly, donation/one_time).
  useEffect(() => {
    if (!accessToken) return;
    const intent = readSupportIntent();
    if (!intent) return;
    clearSupportIntent();
    const periodicity = intentMembershipPeriodicity(intent);
    if (periodicity) {
      void runMembership(periodicity);
    } else {
      void runDonation();
    }
  }, [accessToken]);

  const chooseDonation = () => {
    if (!accessToken) {
      storeSupportIntent("donation/one_time");
      openLogin();
      return;
    }
    void runDonation();
  };

  const chooseSupporter = (periodicity: "monthly" | "yearly") => {
    if (!accessToken) {
      storeSupportIntent(`membership/supporter/${periodicity}`);
      openLogin();
      return;
    }
    void runMembership(periodicity);
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

  const hasIntent = readSupportIntent() !== null;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Hero */}
      <section className="text-center">
        <h1 className="text-2xl font-semibold">💚 {t("osapSupport.title")}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-osap-muted">{t("osapSupport.context")}</p>
      </section>

      {/* ¿Cómo quieres ayudar? */}
      <section>
        <h2 className="text-center text-lg font-semibold">{t("osapSupport.chooseTitle")}</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {/* Donación */}
          <div className="flex flex-col rounded border border-osap-border bg-osap-surface p-5 text-center">
            <h3 className="text-base font-semibold">{t("osapSupport.donationTitle")}</h3>
            <p className="mt-1 text-sm text-osap-muted">{t("osapSupport.donationSub")}</p>
            <div className="mt-4">
              <label className="block text-sm font-medium" htmlFor="donation-amount">
                {t("osapSupport.donationAmount")}
              </label>
              <input
                id="donation-amount"
                type="number"
                min={1}
                step={0.01}
                value={donationAmount}
                onChange={(e) => setDonationAmount(e.target.value)}
                className="mx-auto mt-2 w-32 rounded border border-osap-border bg-osap-bg px-3 py-2 text-center"
              />
            </div>
            <div className="mt-4 flex flex-1 flex-col justify-end">
              <Button onClick={chooseDonation} disabled={starting}>
                {starting ? "…" : t("osapSupport.donateCta")}
              </Button>
              {actionError && <p className="mt-2 text-xs text-red-500">{actionError}</p>}
            </div>
          </div>

          {/* Supporter */}
          <div className="flex flex-col rounded border border-osap-border bg-osap-surface p-5 text-center">
            <h3 className="text-base font-semibold">{t("osapSupport.supporterTitle")}</h3>
            {support.authenticated && support.status === "loading" ? (
              <p className="mt-3 text-sm text-osap-muted">…</p>
            ) : activeSupporter ? (
              <div className="mt-3 flex flex-1 flex-col justify-center">
                <p className="text-sm font-medium text-osap-accent">{t("osapSupport.activeMember")}</p>
                <p className="mt-1 text-sm text-osap-muted">{t("osapSupport.activePlan")}</p>
                <p className="mt-1 text-sm text-osap-muted">
                  {membershipView?.periodicity === "yearly"
                    ? t("osapSupport.planYearly")
                    : t("osapSupport.planMonthly")}
                </p>
              </div>
            ) : statusText ? (
              <p className="mt-3 text-sm text-osap-muted">{statusText}</p>
            ) : (
              <>
                <p className="mt-1 text-sm text-osap-muted">{t("osapSupport.supporterSub")}</p>
                <div className="mt-4 space-y-3">
                  {SUPPORTER_PLANS.map((plan) => (
                    <div
                      key={plan.periodicity}
                      className="rounded border border-osap-border bg-osap-bg p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-left">
                          <p className="text-sm font-semibold">{t(plan.titleKey)}</p>
                          <p className="text-xs text-osap-muted">{t(plan.priceKey)}</p>
                        </div>
                        <Button
                          onClick={() => chooseSupporter(plan.periodicity)}
                          disabled={membershipStarting !== null}
                        >
                          {membershipStarting === plan.periodicity ? "…" : t(plan.ctaKey)}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
                {membershipError && <p className="mt-3 text-xs text-red-500">{membershipError}</p>}
              </>
            )}
          </div>
        </div>
      </section>

      {/* ¿Por qué necesitamos apoyo? */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.whyTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.whyIntro")}</p>
        <ul className="mt-4 flex flex-wrap justify-center gap-2">
          {[
            t("osapSupport.whyInfra"),
            t("osapSupport.whyDev"),
            t("osapSupport.whyMaint"),
            t("osapSupport.whyResearch"),
            t("osapSupport.whyTime"),
          ].map((item) => (
            <li
              key={item}
              className="rounded-full border border-osap-border bg-osap-bg px-3 py-1 text-sm"
            >
              {item}
            </li>
          ))}
        </ul>
      </section>

      {/* Tu cuenta es tu relación con OSAP */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.accountTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.accountIntro")}</p>
        <ul className="mt-3 grid gap-1 text-sm sm:grid-cols-2">
          {[
            t("osapSupport.accountBullet1"),
            t("osapSupport.accountBullet2"),
            t("osapSupport.accountBullet3"),
            t("osapSupport.accountBullet4"),
          ].map((item) => (
            <li key={item}>• {item}</li>
          ))}
        </ul>
      </section>

      {/* Privacidad */}
      <section className="rounded border border-osap-border bg-osap-surface p-5">
        <h2 className="text-lg font-semibold">{t("osapSupport.privacyTitle")}</h2>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.privacyBody")}</p>
        <p className="mt-2 text-sm text-osap-muted">{t("osapSupport.privacyRecognition")}</p>
      </section>

      {/* Cuenta — SOLO tras elegir (flujo Resolver) */}
      {authOpen && !support.authenticated && hasIntent && (
        <section className="rounded border border-osap-border bg-osap-surface p-5">
          <p className="text-sm text-osap-muted">{t("osapSupport.accountPrompt")}</p>
          {oidcError && <p className="mt-2 text-xs text-red-500">{oidcError}</p>}
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
        </section>
      )}
    </div>
  );
}
