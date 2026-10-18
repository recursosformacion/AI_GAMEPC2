import { useEffect } from "react";
import { useI18n } from "../i18n/I18n";
import { useNotifications } from "../state/notifications";

// Bandeja de la campana: avisos del usuario (y globales si es admin), con estado leído.
export function NotificationsPage() {
  const { t } = useI18n();
  const { items, unread, load, markRead, markAll } = useNotifications();

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-osap-ink">{t("notifications.title")}</h1>
        {unread > 0 ? (
          <button
            type="button"
            onClick={() => void markAll()}
            className="text-sm text-osap-accent hover:underline"
          >
            {t("notifications.markAll")}
          </button>
        ) : null}
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-osap-muted">{t("notifications.empty")}</p>
      ) : (
        <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface">
          {items.map((notification) => (
            <li
              key={notification.id}
              className={`p-3 ${notification.read_at ? "opacity-70" : ""}`}
            >
              <button
                type="button"
                onClick={() => void markRead(notification.id)}
                className="w-full text-left"
              >
                <p className="text-sm font-medium text-osap-ink">{notification.title}</p>
                <p className="mt-1 text-sm text-osap-muted">{notification.body}</p>
                <p className="mt-1 text-xs text-osap-muted">
                  {notification.created_at.slice(0, 10)}
                </p>
              </button>
              {notification.link ? (
                <a
                  href={notification.link}
                  className="mt-1 inline-block text-xs text-osap-accent hover:underline"
                >
                  {notification.link}
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
