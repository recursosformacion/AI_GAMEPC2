import { useEffect } from "react";
import { I18nProvider } from "./i18n/I18n";
import { AppRoutes } from "./routing/routes";
import { useAuth } from "./state/auth";
import { usePreferences } from "./state/preferences";

// Cierre de sesión automático por inactividad (1 hora sin actividad del usuario).
const IDLE_MS = 60 * 60 * 1000;

const ACTIVITY_EVENTS = ["mousemove", "keydown", "click", "scroll", "touchstart"] as const;

function useIdleLogout(ms: number) {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const reset = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (useAuth.getState().isAuthenticated()) useAuth.getState().logout();
      }, ms);
    };
    ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, reset, { passive: true }));
    reset();
    return () => {
      if (timer) clearTimeout(timer);
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, reset));
    };
  }, [ms]);
}

export default function App() {
  const lang = usePreferences((s) => s.lang);
  const setLang = usePreferences((s) => s.setLang);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  useEffect(() => {
    // Rehidratación de sesión al arrancar (refresco proactivo si hay refresh en localStorage).
    void useAuth.getState().rehydrate();
  }, []);
  useIdleLogout(IDLE_MS);
  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <AppRoutes />
    </I18nProvider>
  );
}
