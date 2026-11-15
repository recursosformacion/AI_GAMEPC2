import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/ApiClient";
import { Button } from "../components/Button";
import type { AmigosGroup } from "../api/types";

interface Manager {
  user_id: string;
  name?: string | null;
  email?: string | null;
}

interface AdminEntity {
  id: string;
  name: string;
  kind: string;
  email: string | null;
  representative_user_id: string | null;
  representative_name: string | null;
  managers: Manager[];
}

interface AdminUserOption {
  user_id: string;
  name?: string | null;
  nickname?: string | null;
  email?: string | null;
}

const KINDS = [
  ["coral", "Coral"],
  ["orquesta", "Orquesta"],
  ["grupo", "Grupo"],
  ["banda", "Banda"],
  ["ensemble", "Ensemble"],
  ["escuela", "Escuela"],
  ["iglesia", "Iglesia"],
] as const;

type Draft = {
  group_id: string;
  name: string;
  kind: string;
  email: string;
  manager_user_id: string;
};

const EMPTY_DRAFT: Draft = {
  group_id: "",
  name: "",
  kind: "coral",
  email: "",
  manager_user_id: "",
};

export default function AdminEntitiesPage() {
  const [entities, setEntities] = useState<AdminEntity[]>([]);
  const [users, setUsers] = useState<AdminUserOption[]>([]);
  const [groups, setGroups] = useState<AmigosGroup[]>([]);
  const [selected, setSelected] = useState<AdminEntity | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [managerId, setManagerId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [entityRows, userRows, groupRows] = await Promise.all([
      apiClient.get<AdminEntity[]>("/admin/entities"),
      apiClient.get<AdminUserOption[]>("/admin/users"),
      apiClient.getAmigosGroups(true),
    ]);
    setEntities(entityRows);
    setUsers(userRows);
    setGroups(groupRows);
    setSelected((current) =>
      current ? entityRows.find((item) => item.id === current.id) ?? null : null,
    );
  };

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error al cargar"));
  }, []);

  const selectedGroup = groups.find((group) => group.id === selected?.id);

  const availableManagers = useMemo(
    () =>
      users.filter(
        (user) => !(selected?.managers ?? []).some((manager) => manager.user_id === user.user_id),
      ),
    [users, selected],
  );

  const beginCreate = () => {
    setCreating(true);
    setSelected(null);
    setDraft(EMPTY_DRAFT);
    setMessage(null);
    setError(null);
  };

  const beginLinkGroup = (group: AmigosGroup) => {
    setCreating(true);
    setSelected(null);
    setDraft({
      group_id: group.id,
      name: group.name,
      kind: String(group.kind),
      email: group.email ?? "",
      manager_user_id: "",
    });
    setMessage(null);
    setError(null);
  };

  const beginEdit = (entity: AdminEntity) => {
    setCreating(false);
    setSelected(entity);
    setDraft({
      group_id: entity.id,
      name: entity.name,
      kind: entity.kind,
      email: entity.email ?? "",
      manager_user_id: "",
    });
    setMessage(null);
    setError(null);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      if (creating) {
        const created = await apiClient.post<AdminEntity>("/admin/entities", {
          name: draft.name.trim(),
          kind: draft.kind,
          email: draft.email.trim() || null,
          manager_user_id: draft.manager_user_id || null,
          entity_id: draft.group_id || null,
        });
        setMessage("Entidad creada.");
        setCreating(false);
        setSelected(created);
      } else if (selected) {
        const updated = await apiClient.patch<AdminEntity>(
          `/admin/entities/${encodeURIComponent(selected.id)}`,
          {
            name: draft.name.trim(),
            kind: draft.kind,
            email: draft.email.trim() || null,
          },
        );
        setMessage("Entidad actualizada.");
        setSelected(updated);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setSaving(false);
    }
  };

  const syncFromAmigos = async () => {
    if (!selected || !selectedGroup) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.patch<AdminEntity>(
        `/admin/entities/${encodeURIComponent(selected.id)}`,
        { name: selectedGroup.name, kind: selectedGroup.kind, email: selectedGroup.email || null },
      );
      setSelected(updated);
      setMessage("Datos sincronizados desde Amigos.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo sincronizar");
    } finally {
      setSaving(false);
    }
  };

  const addManager = async () => {
    if (!selected || !managerId) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.post<AdminEntity>(
        `/admin/entities/${encodeURIComponent(selected.id)}/managers`,
        { user_id: managerId },
      );
      setSelected(updated);
      setManagerId("");
      setMessage("Gestor añadido.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo añadir el gestor");
    } finally {
      setSaving(false);
    }
  };

  const removeManager = async (userId: string) => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.delete<AdminEntity>(
        `/admin/entities/${encodeURIComponent(selected.id)}/managers/${encodeURIComponent(userId)}`,
      );
      setSelected(updated);
      setMessage("Gestor retirado.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo retirar el gestor");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
            Administración
          </p>
          <h1 className="mt-1 text-3xl font-semibold">Entidades</h1>
          <p className="mt-1 max-w-2xl text-sm text-osap-muted">
            Acceso y gestores de las entidades. Los datos públicos se mantienen en
            Amigos · Corales; aquí se enlaza el grupo y se asignan sus gestores de Chorus.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a
            href="/admin/amigos/nuevo"
            target="_blank"
            rel="noreferrer"
            className="text-sm text-osap-accent hover:underline"
          >
            Crear entidad en Amigos
          </a>
          <Button onClick={beginCreate}>Vincular grupo existente</Button>
        </div>
      </header>

      {error && <p className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded border border-green-200 bg-green-50 p-2 text-sm text-green-700">{message}</p>}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
        <section className="overflow-hidden rounded-card border border-osap-border bg-osap-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-osap-border text-xs uppercase tracking-wide text-osap-muted">
              <tr>
                <th className="p-3">Entidad</th>
                <th className="p-3">Tipo</th>
                <th className="p-3">Gestores</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-osap-border">
              {groups.length === 0 ? (
                <tr><td className="p-4 text-osap-muted" colSpan={4}>Sin grupos en Amigos.</td></tr>
              ) : groups.map((group) => {
                const entity = entities.find((item) => item.id === group.id);
                return (
                  <tr key={group.id} className={selected?.id === group.id ? "bg-osap-bg" : ""}>
                    <td className="p-3">
                      <strong>{group.name}</strong>
                      {group.email ? <div className="text-xs text-osap-muted">{group.email}</div> : null}
                      {entity ? null : <span className="ml-2 text-xs text-osap-muted">Sin acceso</span>}
                    </td>
                    <td className="p-3">{group.kind}</td>
                    <td className="p-3">
                      {!entity || entity.managers.length === 0
                        ? <span className="text-osap-muted">Sin gestor</span>
                        : entity.managers.map((manager) => manager.name || manager.user_id).join(", ")}
                    </td>
                    <td className="p-3 text-right">
                      {entity ? (
                        <Button onClick={() => beginEdit(entity)}>Gestionar</Button>
                      ) : (
                        <Button onClick={() => beginLinkGroup(group)}>Vincular</Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="rounded-card border border-osap-border bg-osap-surface p-4">
          {!creating && !selected ? (
            <p className="text-sm text-osap-muted">Selecciona una entidad o crea una nueva.</p>
          ) : (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">
                {creating ? "Nueva entidad" : `Editar ${selected?.name}`}
              </h2>
              {creating ? (
                <label className="block text-sm">
                  Grupo de Amigos
                  <select
                    className="mt-1 w-full rounded border border-osap-border px-2 py-1.5"
                    value={draft.group_id}
                    onChange={(e) => {
                      const group = groups.find((item) => item.id === e.target.value);
                      setDraft({
                        ...draft,
                        group_id: e.target.value,
                        name: group?.name ?? "",
                        kind: group?.kind ?? "coral",
                        email: group?.email ?? "",
                      });
                    }}
                  >
                    <option value="">— Elegir grupo —</option>
                    {groups
                      .filter((group) => !entities.some((entity) => entity.id === group.id))
                      .map((group) => (
                        <option key={group.id} value={group.id}>
                          {group.name} ({group.kind})
                        </option>
                      ))}
                  </select>
                </label>
              ) : selected ? (
                <a
                  href={`/admin/amigos/${encodeURIComponent(selected.id)}?mode=edit`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-osap-accent hover:underline"
                >
                  Editar la ficha pública en Amigos →
                </a>
              ) : null}
              <p className="text-xs text-osap-muted">
                Nombre, tipo y correo se mantienen en Amigos; aquí solo se sincronizan.
              </p>
              {selectedGroup ? (
                <Button disabled={saving} onClick={() => void syncFromAmigos()}>
                  Sincronizar desde Amigos
                </Button>
              ) : null}
              <label className="block text-sm">
                Nombre
                <input
                  className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-1.5"
                  value={draft.name}
                  readOnly
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  Tipo
                  <select
                    className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-1.5"
                    value={draft.kind}
                    disabled
                    onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
                  >
                    {KINDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <label className="block text-sm">
                  Correo de contacto
                  <input
                    className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-1.5"
                    value={draft.email}
                    readOnly
                    onChange={(e) => setDraft({ ...draft, email: e.target.value })}
                  />
                </label>
              </div>
              {creating ? (
                <label className="block text-sm">
                  Gestor inicial
                  <select
                    className="mt-1 w-full rounded border border-osap-border px-2 py-1.5"
                    value={draft.manager_user_id}
                    onChange={(e) => setDraft({ ...draft, manager_user_id: e.target.value })}
                  >
                    <option value="">— Sin gestor —</option>
                    {users.map((user) => (
                      <option key={user.user_id} value={user.user_id}>
                        {user.nickname || user.name || user.email || user.user_id}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <div className="flex gap-2">
                <Button disabled={saving || !draft.name.trim() || (creating && !draft.group_id)} onClick={() => void save()}>
                  {creating ? "Crear" : "Guardar"}
                </Button>
                <Button onClick={() => { setCreating(false); setSelected(null); }}>Cancelar</Button>
              </div>

              {!creating && selected ? (
                <div className="space-y-2 border-t border-osap-border pt-3">
                  <h3 className="text-sm font-semibold">Gestores</h3>
                  <ul className="space-y-1 text-sm">
                    {selected.managers.map((manager) => (
                      <li key={manager.user_id} className="flex items-center justify-between gap-2">
                        <span>{manager.name || manager.user_id}</span>
                        <Button disabled={saving} onClick={() => void removeManager(manager.user_id)}>
                          Quitar
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-2">
                    <select
                      className="flex-1 rounded border border-osap-border px-2 py-1.5 text-sm"
                      value={managerId}
                      onChange={(e) => setManagerId(e.target.value)}
                    >
                      <option value="">— Añadir gestor —</option>
                      {availableManagers.map((user) => (
                        <option key={user.user_id} value={user.user_id}>
                          {user.nickname || user.name || user.email || user.user_id}
                        </option>
                      ))}
                    </select>
                    <Button disabled={saving || !managerId} onClick={() => void addManager()}>
                      Añadir
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}








