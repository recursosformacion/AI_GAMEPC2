// "Explorar" — contenedor público del área musical de la v1:
// Discover (temático) · Catálogo · Studio (búsqueda avanzada).

import { Link } from "react-router-dom";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/I18n";

const AREAS = [
  { to: "/discover", titleKey: "nav.discover", icon: "🧭" },
  { to: "/catalog", titleKey: "nav.sources", icon: "📚" },
  { to: "/studio", titleKey: "nav.studio", icon: "🔍" },
] as const;

export function ExplorePage() {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">{t("nav.explore")}</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-osap-muted">{t("explore.intro")}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {AREAS.map((area) => (
          <Link
            key={area.to}
            to={area.to}
            className="rounded border border-osap-border bg-osap-surface p-4 text-center hover:bg-osap-bg"
          >
            <div className="text-2xl">{area.icon}</div>
            <div className="mt-2 font-semibold">{t(area.titleKey)}</div>
          </Link>
        ))}
      </div>
      <div className="text-center">
        <Link to="/discover">
          <Button>{t("nav.discover")}</Button>
        </Link>
      </div>
    </div>
  );
}
