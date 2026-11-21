import { useEffect } from "react";
import { I18nProvider } from "./i18n/I18n";
import { AppRoutes } from "./routing/routes";
import { useAuth, expireSessionIfIdle, getSessionIdleRemainingMs, recordSessionActivity } from "./state/auth";
import { usePreferences } from "./state/preferences";

// La sesión caduca tras 3 horas sin actividad real del usuario.
// Las renovaciones de tokens y las peticiones automáticas no modifican este plazo.
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

function useIdleLogout() {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    const scheduleExpiry = () => {
      if (timer) clearTimeout(timer);
      if (expireSessionIfIdle()) return;
      const remaining = getSessionIdleRemainingMs();
      if (remaining !== null) {
        timer = setTimeout(scheduleExpiry, Math.max(1, remaining));
      }
    };

    const onActivity = () => {
      recordSessionActivity();
      scheduleExpiry();
    };

    ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }));
    // Reprograma el vencimiento también cuando cambia el estado de autenticación
    // (por ejemplo, al terminar la rehidratación tras recargar la página).
    const unsubscribe = useAuth.subscribe(scheduleExpiry);
    scheduleExpiry();

    return () => {
      if (timer) clearTimeout(timer);
      unsubscribe();
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity));
    };
  }, []);
}

export default function App() {
  const lang = usePreferences((s) => s.lang);
  const setLang = usePreferences((s) => s.setLang);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  useEffect(() => {
    // Rehidratación solo si el último uso de la sesión fue hace menos de 3 horas.
    void useAuth.getState().rehydrate();
  }, []);
  useIdleLogout();
  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <AppRoutes />
    </I18nProvider>
  );
}
