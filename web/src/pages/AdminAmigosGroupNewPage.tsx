import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosGroupLink } from "../api/types";
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
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const [groupLinks, setGroupLinks] = useState<AmigosGroupLink[]>([]);
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
        links: groupLinks.filter((l) => l.url.trim() !== ""),
      });
      if (logoFile) {
        const uploaded = await apiClient.uploadAmigosImage(group.id, logoFile);
        await apiClient.updateAmigosGroup(group.id, { logo_url: uploaded.url });
      }
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
          <div className="text-xs text-osap-muted sm:col-span-2">
            <span>{t("friends.logo")}</span>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <input
                value={logoUrl}
                onChange={(e) => setLogoUrl(e.target.value)}
                placeholder="https://…"
                className="min-w-48 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
              <input
                ref={logoInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  setLogoFile(e.target.files?.[0] ?? null);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => logoInputRef.current?.click()}
                className="rounded-md border border-osap-border px-3 py-2 text-sm"
              >
                {logoFile ? logoFile.name : t("friends.upload")}
              </button>
            </div>
          </div>
          <div className="sm:col-span-2">
            <p className="text-xs text-osap-muted">{t("friends.socialLinks")}</p>
            {groupLinks.map((link, i) => (
              <div key={i} className="mt-1 flex flex-wrap items-center gap-2">
                <select
                  value={link.kind}
                  onChange={(e) =>
                    setGroupLinks((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, kind: e.target.value } : r)),
                    )
                  }
                  className="rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm"
                >
                  <option value="facebook">{t("friends.social.facebook")}</option>
                  <option value="instagram">{t("friends.social.instagram")}</option>
                  <option value="other">{t("friends.social.other")}</option>
                </select>
                {link.kind === "other" ? (
                  <input
                    value={link.label ?? ""}
                    onChange={(e) =>
                      setGroupLinks((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, label: e.target.value } : r)),
                      )
                    }
                    className="w-32 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm"
                  />
                ) : null}
                <input
                  value={link.url}
                  onChange={(e) =>
                    setGroupLinks((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, url: e.target.value } : r)),
                    )
                  }
                  placeholder={t("friends.linkUrl")}
                  className="min-w-48 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm"
                />
                <button
                  type="button"
                  onClick={() => setGroupLinks((rows) => rows.filter((_, j) => j !== i))}
                  className="rounded-md border border-osap-border px-3 py-1.5 text-sm text-osap-danger"
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                setGroupLinks((rows) => [...rows, { kind: "facebook", url: "", label: "" }])
              }
              className="mt-1 text-sm text-osap-accent hover:underline"
            >
              + {t("friends.addLink")}
            </button>
          </div>
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
