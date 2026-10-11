import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";

// Alta de un grupo de «Los amigos». Hoy solo hay un tipo (`coral`), pero el formulario ya
// expone el tipo para que añadir tipos futuros no requiera rehacer la pantalla.
export function AdminAmigosGroupNewPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [kind, setKind] = useState("coral");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<"direct" | "moderated">("moderated");
  const [website, setWebsite] = useState("");
  const [email, setEmail] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    if (name.trim() === "") {
      setError(t("friends.titleRequired"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const group = await apiClient.createAmigosGroup({
        name: name.trim(),
        slug: slug.trim() || null,
        kind,
        description: description.trim() || null,
        editorial_mode: mode,
        website: website.trim() || null,
        email: email.trim() || null,
        logo_url: logoUrl.trim() || null,
      });
      navigate(`/admin/amigos/${encodeURIComponent(group.id)}?mode=edit`);
    } catch {
      setError(t("friends.errorSaving"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          {t("nav.sectionFriends")} · {t("friends.adminNewGroup")}
        </h1>
        <Link to="/admin/amigos" className="text-sm text-osap-accent hover:underline">
          ← {t("friends.adminGrupos")}
        </Link>
      </div>

      <Card title={t("friends.adminNewGroup")}>
        {error ? <p className="mb-2 text-sm text-red-500">{error}</p> : null}
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-osap-muted">
            {t("friends.groupName")} *
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.slug")}
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="ctv"
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.kind")}
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value)}
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            >
              <option value="coral">{t("nav.corales")}</option>
            </select>
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.editorialMode")}
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value === "direct" ? "direct" : "moderated")}
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            >
              <option value="moderated">{t("friends.modeModerated")}</option>
              <option value="direct">{t("friends.modeDirect")}</option>
            </select>
          </label>
          <label className="text-xs text-osap-muted sm:col-span-2">
            {t("friends.description")}
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.website")}
            <input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="https://…"
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.publicEmail")}
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs text-osap-muted sm:col-span-2">
            {t("friends.logo")}
            <input
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://…"
              className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void create()}
            className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {t("friends.create")}
          </button>
          <Link
            to="/admin/amigos"
            className="rounded-md border border-osap-border px-4 py-2 text-sm"
          >
            {t("adminUsers.cancel")}
          </Link>
        </div>
        <p className="mt-2 text-xs text-osap-muted">{t("friends.coralFichaHint")}</p>
      </Card>
    </div>
  );
}
