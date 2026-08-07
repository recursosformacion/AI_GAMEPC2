import { useI18n } from "../i18n/I18n";
import { usePreferences } from "../state/preferences";

export function DarkModeToggle() {
  const { t } = useI18n();
  const dark = usePreferences((s) => s.dark);
  const toggleDark = usePreferences((s) => s.toggleDark);
  return (
    <button
      type="button"
      aria-label={t("theme.dark")}
      onClick={toggleDark}
      className="rounded border border-osap-border px-2 py-1 text-sm"
    >
      {dark ? "☾" : "☀"}
    </button>
  );
}
