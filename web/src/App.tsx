import { I18nProvider } from "./i18n/I18n";
import { AppRoutes } from "./routing/routes";
import { usePreferences } from "./state/preferences";

export default function App() {
  const lang = usePreferences((s) => s.lang);
  const setLang = usePreferences((s) => s.setLang);
  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <AppRoutes />
    </I18nProvider>
  );
}
