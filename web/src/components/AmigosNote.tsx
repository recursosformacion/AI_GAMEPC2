import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";

// Caja informativa de «Los amigos»: va pegada al título, es plegable y por defecto está
// desplegada. Incluye el enlace de contacto.
export function AmigosNote({ titleKey, bodyKey }: { titleKey: TKey; bodyKey: TKey }) {
  const { t } = useI18n();
  return (
    <details
      open
      className="mt-3 rounded-card border border-osap-accent/30 bg-osap-accent-soft px-3 py-2"
    >
      <summary className="cursor-pointer select-none font-semibold text-osap-ink">
        {t(titleKey)}
      </summary>
      <p className="mt-1 text-sm text-osap-ink/80">{t(bodyKey)}</p>
      <Link
        to="/corrections?kind=contact"
        className="mt-1 inline-block text-sm font-medium text-osap-accent hover:underline"
      >
        {t("nav.contact")} →
      </Link>
    </details>
  );
}
