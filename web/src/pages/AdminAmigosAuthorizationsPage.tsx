import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { AmigosAuthorization, AmigosAuthorizationScope } from "../api/types";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";

interface DirectoryUser {
  user_id: string;
  email: string;
  name?: string | null;
  nickname?: string | null;
}

// Gestión de autorizaciones editoriales (blog general y agenda): solo el admin global.
export function AdminAmigosAuthorizationsPage() {
  const { t } = useI18n();
  const [scope, setScope] = useState<AmigosAuthorizationScope>("blog");
  const [rows, setRows] = useState<AmigosAuthorization[]>([]);
  const [users, setUsers] = useState<DirectoryUser[]>([]);
  const [query, setQuery] = useState("");
  const [direct, setDirect] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [auths] = await Promise.all([apiClient.getAmigosAuthorizations(scope)]);
      setRows(auths.items);
    } catch {
      setRows([]);
    }
  }, [scope]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    apiClient
      .get<DirectoryUser[]>("/admin/users")
      .then(setUsers)
      .catch(() => setUsers([]));
  }, []);

  const label = (userId: string) => {
    const u = users.find((x) => x.user_id === userId);
    if (u === undefined) return userId;
    return `${u.name ? u.name + " · " : ""}${u.email}${u.nickname ? ` (${u.nickname})` : ""}`;
  };

  const grant = async () => {
    setError(null);
    const q = query.trim().toLowerCase();
    const user = users.find((u) => u.email.toLowerCase() === q) ?? users.find((u) => u.user_id === query.trim());
    if (user === undefined) {
      setError(t("friends.errorSaving"));
      return;
    }
    try {
      await apiClient.grantAmigosAuthorization(user.user_id, scope, direct);
      setQuery("");
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  const revoke = async (userId: string) => {
    if (!window.confirm(t("friends.confirmRevoke"))) return;
    try {
      await apiClient.revokeAmigosAuthorization(userId, scope);
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-xl font-semibold">
        {t("nav.sectionFriends")} · {t("friends.authorizations")}
      </h1>

      <Card title={t("friends.authorizations")}>
        <div className="flex flex-wrap gap-2">
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value === "events" ? "events" : "blog")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
          >
            <option value="blog">{t("friends.blogTitle")}</option>
            <option value="events">{t("friends.eventsTitle")}</option>
          </select>
          <input
            list="auth-users"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("friends.emailOrUser")}
            className="min-w-64 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
          />
          <datalist id="auth-users">
            {users.map((u) => (
              <option key={u.user_id} value={u.email}>
                {u.name ?? ""}
              </option>
            ))}
          </datalist>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={direct} onChange={(e) => setDirect(e.target.checked)} />
            {t("friends.directPublish")}
          </label>
          <button
            type="button"
            onClick={() => void grant()}
            className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white"
          >
            {t("friends.grant")}
          </button>
        </div>
        {error ? <p className="mt-2 text-sm text-osap-danger">{error}</p> : null}

        <ul className="mt-3 divide-y divide-osap-border">
          {rows.map((a) => (
            <li key={a.user_id} className="flex items-center justify-between py-2 text-sm">
              <span className="min-w-0 truncate" title={a.user_id}>
                {label(a.user_id)}
              </span>
              <span className="flex items-center gap-2 text-xs">
                {a.direct_publish ? (
                  <span className="rounded bg-osap-accent-soft px-2 py-0.5">
                    {t("friends.directPublish")}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={() => void revoke(a.user_id)}
                  className="text-osap-danger hover:underline"
                >
                  {t("friends.revoke")}
                </button>
              </span>
            </li>
          ))}
          {rows.length === 0 ? (
            <li className="py-3 text-sm text-osap-muted">{t("friends.groupsEmpty")}</li>
          ) : null}
        </ul>
      </Card>
    </div>
  );
}
