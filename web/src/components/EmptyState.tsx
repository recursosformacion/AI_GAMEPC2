import { useContext, type ReactNode } from "react";
import { I18nContext } from "../i18n/I18n";
import { translations, type TKey } from "../i18n/translations";

export function EmptyState({ message }: { message?: string }): ReactNode {
  const ctx = useContext(I18nContext);
  const t = ctx?.t ?? ((key: TKey) => translations.en[key]);
  return (
    <div data-testid="empty" className="text-osap-muted">
      {message ?? t("states.empty")}
    </div>
  );
}
