import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../api/ApiClient";
import { authClient, type UserProfile } from "../api/AuthClient";
import type { AmigosGroup, AmigosGroupCatalog, AmigosMyGroup } from "../api/types";
import { useAuth } from "../state/auth";

export function AccountPage() {
  const { user, accessToken, refreshProfile, isAuthenticated } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [groups, setGroups] = useState<AmigosMyGroup[]>([]);
  const [allGroups, setAllGroups] = useState<AmigosGroup[]>([]);
  const [requestGroupId, setRequestGroupId] = useState("");
  const [requestCatalog, setRequestCatalog] = useState<AmigosGroupCatalog>({ admin: [], musical: [], section: [] });
  const [requestAdmin, setRequestAdmin] = useState("");
  const [requestMusical, setRequestMusical] = useState("");
  const [requestSection, setRequestSection] = useState("");
  const [name, setName] = useState(user?.name ?? "");
  const [nickname, setNickname] = useState(user?.nickname ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    if (!accessToken) return;
    try {
      const [me, myGroups, visibleGroups] = await Promise.all([
        authClient.me(accessToken),
        apiClient.getAmigosMyGroups().catch(() => []),
        apiClient.getAmigosGroups().catch(() => []),
      ]);
      setProfile(me);
      setGroups(myGroups);
      setAllGroups(visibleGroups);
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
          Inicia sesión para ver tu ficha.{" "}
          <Link to="/" className="text-osap-accent">
            Volver
          </Link>
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

  const submitRequest = async () => {
    if (!requestGroupId) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.requestAmigosMembership(requestGroupId, {
        admin_role_id: requestAdmin || null,
        musical_role_id: requestMusical || null,
        section_id: requestSection || null,
      });
      setMessage("Solicitud enviada; la administración del grupo debe aprobarla.");
      setRequestGroupId("");
    } catch {
      setError("No se pudo enviar la solicitud.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!requestGroupId) return;
    void apiClient
      .getAmigosGroupCatalog(requestGroupId)
      .then(setRequestCatalog)
      .catch(() => setRequestCatalog({ admin: [], musical: [], section: [] }));
  }, [requestGroupId]);

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

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold">Mi cuenta</h1>
      {error && <p className="text-sm text-red-500">{error}</p>}
      {message && <p className="text-sm text-emerald-600">{message}</p>}

      <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="text-sm font-semibold">Datos de cuenta</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm text-osap-muted">
            Nombre visible
            <input
              value={name}
              disabled={busy}
              onChange={(e) => setName(e.target.value)}
              className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
            />
          </label>
          <label className="grid gap-1 text-sm text-osap-muted">
            Nickname
            <input
              value={nickname}
              disabled={busy}
              onChange={(e) => setNickname(e.target.value)}
              className="rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
            />
          </label>
        </div>
        <button
          className="rounded bg-osap-accent px-3 py-1 text-sm text-white"
          disabled={busy}
          onClick={saveName}
        >
          Guardar nombre y nickname
        </button>
        <p className="text-sm text-osap-muted">Email: {profile?.email ?? user?.email ?? "—"}</p>
        <label className="grid gap-1 text-sm text-osap-muted">
          Teléfono (opcional, para WhatsApp)
          <div className="flex gap-2">
            <input
              value={phone}
              disabled={busy}
              maxLength={32}
              placeholder="+34 600 123 456"
              onChange={(e) => setPhone(e.target.value)}
              className="flex-1 rounded border border-osap-border bg-osap-bg px-3 py-2 text-sm"
            />
            <button
              className="rounded border border-osap-border px-3 py-1 text-sm"
              disabled={busy}
              onClick={savePhone}
            >
              Guardar
            </button>
          </div>
        </label>
      </section>

      <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Grupos y entidades</h2>
          <Link to="/noticias" className="text-sm text-osap-accent hover:underline">
            Noticias
          </Link>
        </div>
        {groups.length === 0 ? (
          <p className="text-sm text-osap-muted">
            No tienes ningún grupo activo. Los gestores pueden invitarte desde la ficha del grupo.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {groups.map(({ group, role }) => (
              <li key={group.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <strong>{group.name}</strong>{" "}
                  <span className="text-osap-muted">
                    ({group.kind === "coral" ? "Coral" : group.kind}) ·{" "}
                    {role === "admin" ? "administración" : "colaborador"}
                  </span>
                </span>
                <Link
                  to={
                    role === "admin"
                      ? `/mis/corales/${encodeURIComponent(group.id)}`
                      : `/amigos/corales/${encodeURIComponent(group.id)}`
                  }
                  className="text-osap-accent hover:underline"
                >
                  Abrir
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="text-sm font-semibold">Solicitar acceso a un grupo</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm text-osap-muted">
            Nombre del grupo
            <select
              value={requestGroupId}
              onChange={(e) => setRequestGroupId(e.target.value)}
              className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-2 text-sm"
            >
              <option value="">— Elegir grupo —</option>
              {allGroups
                .filter(
                  (group) =>
                    !groups.some(({ group: mine, role }) => mine.id === group.id && role),
                )
                .map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} ({group.kind})
                  </option>
                ))}
            </select>
          </label>
          <label className="text-sm text-osap-muted">
            Cargo administrativo
            <select
              value={requestAdmin}
              onChange={(e) => setRequestAdmin(e.target.value)}
              className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-2 text-sm"
            >
              <option value="">Sin cargo</option>
              {requestCatalog.admin.map((item) => (
                <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm text-osap-muted">
            Rol musical
            <select
              value={requestMusical}
              onChange={(e) => setRequestMusical(e.target.value)}
              className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-2 text-sm"
            >
              <option value="">Sin rol musical</option>
              {requestCatalog.musical.map((item) => (
                <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm text-osap-muted">
            Sección / cuerda
            <select
              value={requestSection}
              onChange={(e) => setRequestSection(e.target.value)}
              className="mt-1 w-full rounded border border-osap-border bg-osap-bg px-2 py-2 text-sm"
            >
              <option value="">Sin sección</option>
              {requestCatalog.section.map((item) => (
                <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>
              ))}
            </select>
          </label>
        </div>
        <button
          type="button"
          disabled={!requestGroupId || busy}
          onClick={() => void submitRequest()}
          className="rounded bg-osap-accent px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          Enviar solicitud
        </button>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="text-sm font-semibold">Noticias</h2>
        <p className="mt-1 text-sm text-osap-muted">
          Tus idiomas y temas se eligen en{" "}
          <Link to="/noticias" className="text-osap-accent hover:underline">
            Noticias
          </Link>
          . La lectura no envía correos; el resumen por correo es opcional.
        </p>
      </section>
    </div>
  );
}



