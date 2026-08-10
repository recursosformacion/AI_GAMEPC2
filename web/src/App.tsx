import { useEffect } from "react";
import { I18nProvider } from "./i18n/I18n";
import { AppRoutes } from "./routing/routes";
import { useAuth } from "./state/auth";
import { usePreferences } from "./state/preferences";

export default function App() {
  const lang = usePreferences((s) => s.lang);
  const setLang = usePreferences((s) => s.setLang);
  useEffect(() => {
    // Rehidratación de sesión al arrancar (refresco proactivo si hay refresh en localStorage).
    void useAuth.getState().rehydrate();
  }, []);
  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <AppRoutes />
    </I18nProvider>
  );
}
