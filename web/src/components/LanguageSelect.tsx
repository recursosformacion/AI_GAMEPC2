import { useI18n } from "../i18n/I18n";
import { LANGUAGES } from "../i18n/translations";

export function LanguageSelect() {
  const { lang, setLang } = useI18n();
  return (
    <select
      aria-label="language"
      value={lang}
      onChange={(e) => setLang(e.target.value as typeof lang)}
      className="rounded border border-osap-border bg-osap-surface px-1 py-1 text-sm"
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}
