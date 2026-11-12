import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { authClient, type UserProfile } from "../api/AuthClient";
import type {
  EntityKind,
  EntityListItem,
  EntityMembership,
  EntityRequest,
  MembershipStatus,
} from "../api/types";
import { useAuth } from "../state/auth";

const KIND_LABELS: Record<EntityKind, string> = {
  coral: "Coral",
  orquesta: "Orquesta",
  grupo: "Grupo",
  banda: "Banda",
  ensemble: "Ensemble",
  escuela: "Escuela / Conservatorio",
  iglesia: "Iglesia",
};

const STATUS_LABELS: Record<MembershipStatus, string> = {
  pending: "Pendiente de aprobación",
  approved: "Aprobada",
  rejected: "Rechazada",
};

export function AccountPage() {
  const { user, accessToken, refreshProfile, isAuthenticated } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [entities, setEntities] = useState<EntityListItem[]>([]);
  const [requests, setRequests] = useState<EntityRequest[]>([]);
  const [name, setName] = useState(user?.name ?? "");
  const [nickname, setNickname] = useState(user?.nickname ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [joinEntityId, setJoinEntityId] = useState("");
  const [managedEntityId, setManagedEntityId] = useState("");
  const [entityName, setEntityName] = useState("");
  const [entityKind, setEntityKind] = useState<EntityKind>("coral");
  const [entityEmail, setEntityEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const memberships: EntityMembership[] = profile?.memberships ?? [];
  const managed = memberships.filter((membership) => membership.is_representative);
  const joinable = entities.filter(
    (entity) =>
      !memberships.some(
        (membership) =>
          membership.entity_id === entity.id && membership.status !== "rejected",
      ),
  );

  const reload = async () => {
    if (!accessToken) return;
    try {
      const [me, ents, reqs] = await Promise.all([
        authClient.me(accessToken),
        authClient.listEntities(accessToken),
        authClient.listEntityRequests(accessToken),
      ]);
      setProfile(me);
      setEntities(ents);
      setRequests(reqs);
      setName(me.name ?? "");
      setNickname(me.nickname ?? "");
      setPhone(me.phone ?? "");
      await refreshProfile();
    } catch {
      setError("No se pudo cargar tu ficha de usuario.");
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  if (!isAuthenticated()) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-osap-muted">
          Inicia sesión para ver tu ficha. <Link to="/" className="text-osap-accent">Volver</Link>
        </p>
      </div>
    );
  }

  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      await reload();
      setMessage(success);
    } catch {
      setError("No se pudo guardar el cambio.");
    } finally {
      setBusy(false);
    }
  };

  const saveName = () => {
    if (!accessToken || !name.trim()) {
      setError("Indica tu nombre visible.");
      return;
    }
    if (nickname.trim() && (nickname.trim().length < 3 || nickname.trim().length > 30)) {
      setError("El nickname debe tener entre 3 y 30 caracteres.");
      return;
    }
    void run(
      () => authClient.updateMe(accessToken, name.trim(), nickname.trim() || undefined),
      "Datos actualizados.",
    );
  };

  const savePhone = () => {
    if (!accessToken) return;
    const cleaned = phone.replace(/[\s().\-/]/g, "");
    if (cleaned && !/^\+?[0-9]{7,15}$/.test(cleaned)) {
      setError("Teléfono inválido: usa 7-15 dígitos con + opcional.");
      return;
    }
    void run(
      () => authClient.updatePhone(accessToken, phone.trim() || null),
      phone.trim() ? "Teléfono guardado." : "Teléfono eliminado.",
    );
  };

  const join = () => {
    if (!accessToken || !joinEntityId) {
      setError("Elige una entidad de la lista.");
      return;
    }
    void run(
      () => authClient.updateMyEntity(accessToken, { action: "join", entity_id: joinEntityId }),
      "Solicitud enviada. La entidad debe aprobarla para que seas miembro.",
    );
  };

  const leave = (membership: EntityMembership) => {
    if (!accessToken) return;
    void run(
      () =>
        authClient.updateMyEntity(accessToken, {
          action: "leave",
          entity_id: membership.entity_id,
        }),
      `Has dejado «${membership.entity_name}».`,
    );
  };

  const selectManaged = (entityId: string) => {
    setManagedEntityId(entityId);
    const selected = managed.find((membership) => membership.entity_id === entityId);
    setEntityName(selected?.entity_name ?? "");
    setEntityKind(selected?.entity_kind ?? "coral");
    setEntityEmail(selected?.entity_email ?? "");
  };

  const represent = () => {
    if (!accessToken || !entityName.trim()) {
      setError("Indica el nombre de la entidad que representas.");
      return;
    }
    if (!entityEmail.trim()) {
      setError("Indica el correo de contacto de la entidad.");
      return;
    }
    void run(
      () =>
        authClient.updateMyEntity(accessToken, {
          action: "represent",
          entity_id: managedEntityId || undefined,
          entity_name: entityName.trim(),
          entity_kind: entityKind,
          entity_email: entityEmail.trim(),
        }),
      managedEntityId ? "Entidad actualizada." : "Entidad creada.",
    );
  };

  const decide = (request: EntityRequest, action: "approve" | "reject") => {
    if (!accessToken) return;
    void run(
      () => authClient.decideEntityRequest(accessToken, request.id, action),
      action === "approve"
        ? `Incorporación de «${request.nickname ?? request.name ?? request.user_id}» aprobada.`
        : `Solicitud de «${request.nickname ?? request.name ?? request.user_id}» rechazada.`,
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold">Mi cuenta</h1>
      {error && <p className="text-sm text-red-500">{error}</p>}
      {message && <p className="text-sm text-emerald-600">{message}</p>}

      <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="text-sm font-semibold">Datos de cuenta</h2>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-name">Nombre visible</label>
          <input
            id="account-name"
            value={name}
            disabled={busy}
            onChange={(e) => setName(e.target.value)}
            className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
          />
        </div>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-nickname">Nickname</label>
          <input
            id="account-nickname"
            value={nickname}
            disabled={busy}
            minLength={3}
            maxLength={30}
            placeholder="3-30 caracteres"
            onChange={(e) => setNickname(e.target.value)}
            className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
          />
        </div>
        <button className="rounded bg-osap-accent px-3 py-1 text-sm text-white" disabled={busy} onClick={saveName}>
          Guardar nombre y nickname
        </button>
        <div className="grid gap-1 text-sm">
          <span className="text-osap-muted">Email</span>
          <span>{profile?.email ?? user?.email ?? "—"}</span>
        </div>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-phone">
            Teléfono (opcional, para WhatsApp)
          </label>
          <div className="flex gap-2">
            <input
              id="account-phone"
              type="tel"
              value={phone}
              disabled={busy}
              maxLength={32}
              placeholder="+34 600 123 456"
              onChange={(e) => setPhone(e.target.value)}
              className="flex-1 rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
            />
            <button className="rounded border border-osap-border px-3 py-1 text-sm" disabled={busy} onClick={savePhone}>
              Guardar
            </button>
          </div>
        </div>
      </section>

      <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="text-sm font-semibold">Entidades</h2>
        {memberships.length === 0 ? (
          <p className="text-sm text-osap-muted">No tienes ninguna pertenencia ni solicitud.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {memberships.map((membership) => (
              <li key={membership.id} className="flex flex-wrap items-center gap-2">
                <span>
                  <strong>{membership.entity_name}</strong> ({KIND_LABELS[membership.entity_kind]}) —{" "}
                  {STATUS_LABELS[membership.status]}
                  {membership.entity_email ? ` · ${membership.entity_email}` : ""}
                  {membership.is_representative ? " · la representas" : ""}
                </span>
                {membership.status !== "rejected" ? (
                  <button
                    className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-600"
                    disabled={busy}
                    onClick={() => leave(membership)}
                  >
                    Dejar
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-osap-muted">
          Una solicitud no es una pertenencia hasta que el gestor de la entidad la aprueba.
        </p>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-join">Solicitar pertenecer a</label>
          <div className="flex gap-2">
            <select
              id="account-join"
              value={joinEntityId}
              disabled={busy}
              onChange={(e) => setJoinEntityId(e.target.value)}
              className="flex-1 rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
            >
              <option value="">— Ninguna —</option>
              {joinable.map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name} ({KIND_LABELS[entity.kind]})
                </option>
              ))}
            </select>
            <button className="rounded bg-osap-accent px-3 py-1 text-sm text-white" disabled={busy || !joinEntityId} onClick={join}>
              Enviar solicitud
            </button>
          </div>
        </div>
      </section>

      <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="text-sm font-semibold">Representar una entidad</h2>
        <p className="text-xs text-osap-muted">
          Crea una entidad nueva o actualiza una que ya gestionas. Su nombre se ofrecerá a futuros usuarios.
        </p>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-managed">Entidad que gestionas</label>
          <select
            id="account-managed"
            value={managedEntityId}
            disabled={busy}
            onChange={(e) => selectManaged(e.target.value)}
            className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
          >
            <option value="">— Nueva entidad —</option>
            {managed.map((membership) => (
              <option key={membership.id} value={membership.entity_id}>
                {membership.entity_name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-entity-name">Nombre</label>
          <input
            id="account-entity-name"
            value={entityName}
            disabled={busy}
            maxLength={120}
            placeholder="Coral nnnnn / Orquesta kkkkk / Grup sss"
            onChange={(e) => setEntityName(e.target.value)}
            className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
          />
        </div>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-entity-kind">Tipo</label>
          <select
            id="account-entity-kind"
            value={entityKind}
            disabled={busy}
            onChange={(e) => setEntityKind(e.target.value as EntityKind)}
            className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
          >
            {Object.entries(KIND_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1">
          <label className="text-sm text-osap-muted" htmlFor="account-entity-email">Correo de contacto</label>
          <input
            id="account-entity-email"
            type="email"
            value={entityEmail}
            disabled={busy}
            maxLength={254}
            placeholder="contacto@entidad.example"
            onChange={(e) => setEntityEmail(e.target.value)}
            className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
          />
        </div>
        <button className="rounded bg-osap-accent px-3 py-1 text-sm text-white" disabled={busy} onClick={represent}>
          {managedEntityId ? "Actualizar entidad" : "Crear entidad"}
        </button>
      </section>

      {requests.length > 0 ? (
        <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
          <h2 className="text-sm font-semibold">Solicitudes de ingreso pendientes</h2>
          <ul className="space-y-2 text-sm">
            {requests.map((request) => (
              <li key={request.id} className="flex flex-wrap items-center gap-2">
                <span>
                  <strong>{request.nickname ?? request.name ?? request.user_id}</strong> solicita unirse a{" "}
                  <strong>{request.entity_name}</strong> ({KIND_LABELS[request.entity_kind]})
                </span>
                <button
                  className="rounded bg-osap-accent px-2 py-0.5 text-xs text-white"
                  disabled={busy}
                  onClick={() => decide(request, "approve")}
                >
                  Aprobar
                </button>
                <button
                  className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-600"
                  disabled={busy}
                  onClick={() => decide(request, "reject")}
                >
                  Rechazar
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
