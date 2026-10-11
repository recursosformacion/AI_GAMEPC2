import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosGroup } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";

// Mantenimiento de «Los amigos»: listado con columnas relevantes, búsqueda, orden por
// columna y acciones (ver / editar / dar de baja) como iconos — mismo patrón que el resto
// de mantenimientos del Admin. Con `kind` se reutiliza el índice para «Corales».
function Icon({ children, title }: { children: ReactNode; title: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      role="img"
      aria-label={title}
    >
      {children}
    </svg>
  );
}

type SortKey = "name" | "slug" | "kind" | "editorial_mode" | "status";

const STATUS_KEY: Record<string, TKey> = {
  active: "friends.active",
  inactive: "friends.inactive",
  dissolved: "friends.dissolved",
};

export function AdminAmigosGroupsPage({ kind }: { kind?: string } = {}) {
  const { t } = useI18n();
  const [groups, setGroups] = useState<AmigosGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "name", dir: 1 });
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setGroups(await apiClient.getAmigosGroups(true, kind));
    } catch {
      setGroups([]);
    } finally {
      setLoading(false);
    }
  }, [kind]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered =
      q === ""
        ? groups
        : groups.filter((g) =>
            [g.name, g.slug, g.description ?? ""].some((v) => v.toLowerCase().includes(q)),
          );
    return [...filtered].sort((a, b) => {
      const av = String(a[sort.key] ?? "").toLowerCase();
      const bv = String(b[sort.key] ?? "").toLowerCase();
      return av < bv ? -sort.dir : av > bv ? sort.dir : 0;
    });
  }, [groups, query, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));

  const toggleStatus = async (g: AmigosGroup) => {
    if (g.status === "active" && !window.confirm(t("friends.confirmBaja"))) return;
    setBusyId(g.id);
    setError(null);
    try {
      await apiClient.updateAmigosGroup(g.id, {
        status: g.status === "active" ? "inactive" : "active",
      });
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    } finally {
      setBusyId(null);
    }
  };

  const kindLabel = (k: string) => (k === "coral" ? t("nav.corales") : k);
  const iconBtn = "rounded p-1.5 hover:bg-osap-surface";
  const Th = ({ k, label }: { k: SortKey; label: string }) => (
    <th className="px-3 py-2">
      <button
        type="button"
        onClick={() => toggleSort(k)}
        className="inline-flex items-center gap-1 hover:text-osap-accent"
      >
        {label}
        {sort.key === k ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
      </button>
    </th>
  );

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">
          {t("nav.sectionFriends")} ·{" "}
          {kind === "coral" ? t("nav.corales") : t("friends.adminGrupos")}
        </h1>
        <Link
          to="/admin/amigos/nuevo"
          className="rounded-md bg-osap-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-osap-accent/90"
        >
          {t("friends.adminNewGroup")}
        </Link>
      </div>

      <div className="mt-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("friends.search")}
          className="w-full max-w-sm rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        />
      </div>

      {error ? <p className="mt-2 text-sm text-red-500">{error}</p> : null}

      {loading ? (
        <Spinner />
      ) : (
        <div className="mt-4 overflow-x-auto rounded border border-osap-border bg-osap-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-osap-border text-left">
              <tr>
                <Th k="name" label={t("friends.groupName")} />
                <Th k="slug" label={t("friends.slug")} />
                <Th k="kind" label={t("friends.kind")} />
                <Th k="editorial_mode" label={t("friends.editorialMode")} />
                <Th k="status" label={t("friends.active")} />
                <th className="px-3 py-2 text-right">{t("adminUsers.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((g) => {
                const isActive = g.status === "active";
                return (
                  <tr key={g.id} className="border-b border-osap-border last:border-0">
                    <td className="px-3 py-2">{g.name}</td>
                    <td className="px-3 py-2 text-osap-muted">/{g.slug}</td>
                    <td className="px-3 py-2">{kindLabel(g.kind)}</td>
                    <td className="px-3 py-2">
                      {g.editorial_mode === "direct"
                        ? t("friends.modeDirect")
                        : t("friends.modeModerated")}
                    </td>
                    <td className="px-3 py-2">{t(STATUS_KEY[g.status] ?? "friends.active")}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center justify-end gap-1 text-osap-accent">
                        <Link
                          to={`/admin/amigos/${encodeURIComponent(g.id)}?mode=view`}
                          title={t("adminUsers.view")}
                          className={iconBtn}
                        >
                          <Icon title={t("adminUsers.view")}>
                            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                            <circle cx="12" cy="12" r="3" />
                          </Icon>
                        </Link>
                        <Link
                          to={`/admin/amigos/${encodeURIComponent(g.id)}?mode=edit`}
                          title={t("adminUsers.edit")}
                          className={iconBtn}
                        >
                          <Icon title={t("adminUsers.edit")}>
                            <path d="M12 20h9" />
                            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
                          </Icon>
                        </Link>
                        <button
                          type="button"
                          disabled={busyId === g.id}
                          onClick={() => void toggleStatus(g)}
                          title={isActive ? t("friends.deactivate") : t("friends.reactivate")}
                          className={`${iconBtn} ${isActive ? "text-red-500" : "text-emerald-600"}`}
                        >
                          <Icon title={isActive ? t("friends.deactivate") : t("friends.reactivate")}>
                            {isActive ? (
                              <>
                                <circle cx="12" cy="12" r="9" />
                                <path d="M9 9l6 6M15 9l-6 6" />
                              </>
                            ) : (
                              <>
                                <circle cx="12" cy="12" r="9" />
                                <path d="M8 12l3 3 5-6" />
                              </>
                            )}
                          </Icon>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && !error ? (
                <tr>
                  <td colSpan={6} className="px-3 py-4 text-center text-osap-muted">
                    {t("friends.groupsEmpty")}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
