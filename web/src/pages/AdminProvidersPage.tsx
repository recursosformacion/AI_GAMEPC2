import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { OpProvider } from "../api/types";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import type { Language } from "../i18n/translations";

const LANG_CODES: Language[] = ["es", "ca", "fr", "en", "de"];

function parseJson(raw: string): Record<string, unknown> | null {
  try {
    const v = JSON.parse(raw || "{}");
    return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  } catch {
    return null;
  }
}

function asString(v: unknown): string {
  if (v === null || v === undefined) return "";
  return typeof v === "string" ? v : JSON.stringify(v, null, 2);
}

function asDescription(v: OpProvider["description"]): Record<string, string> {
  if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, string>;
  if (typeof v === "string") return { en: v };
  return {};
}

interface FormState {
  provider_id: string;
  name: string;
  base_url: string;
  wired: boolean;
  descriptions: Record<Language, string>;
  endpoints: string;
  mapping: string;
  resources: string;
  transforms: string;
}

const EMPTY_FORM: FormState = {
  provider_id: "",
  name: "",
  base_url: "",
  wired: false,
  descriptions: { es: "", ca: "", fr: "", en: "", de: "" },
  endpoints: "{}",
  mapping: "{}",
  resources: "{}",
  transforms: "{}",
};

export function AdminProvidersPage() {
  const { t, lang } = useI18n();
  const [items, setItems] = useState<OpProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null); // null = alta
  const [viewing, setViewing] = useState<string | null>(null); // modo ver (solo lectura)
  const [descTab, setDescTab] = useState<Language>(lang);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await apiClient.listOpProviders());
      setError(null);
    } catch {
      setError(t("admin.providersLoadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const desc = (p: OpProvider): string =>
    asDescription(p.description)[lang] ?? asDescription(p.description).en ?? "";

  const startNew = () => {
    setEditing(null);
    setViewing(null);
    setForm(EMPTY_FORM);
    setDescTab(lang);
  };

  const startView = (p: OpProvider) => {
    setViewing(p.provider_id);
    setEditing(null);
    setForm({
      provider_id: p.provider_id,
      name: p.name,
      base_url: p.base_url ?? "",
      wired: p.wired ? true : false,
      descriptions: {
        es: asDescription(p.description).es ?? "",
        ca: asDescription(p.description).ca ?? "",
        fr: asDescription(p.description).fr ?? "",
        en: asDescription(p.description).en ?? "",
        de: asDescription(p.description).de ?? "",
      },
      endpoints: asString(p.endpoints),
      mapping: asString(p.mapping),
      resources: asString(p.resources),
      transforms: asString(p.transforms),
    });
    setDescTab(lang);
  };

  const startEdit = (p: OpProvider) => {
    setViewing(null);
    setEditing(p.provider_id);
    const descriptions = asDescription(p.description);
    setForm({
      provider_id: p.provider_id,
      name: p.name,
      base_url: p.base_url ?? "",
      wired: p.wired ? true : false,
      descriptions: {
        es: descriptions.es ?? "",
        ca: descriptions.ca ?? "",
        fr: descriptions.fr ?? "",
        en: descriptions.en ?? "",
        de: descriptions.de ?? "",
      },
      endpoints: asString(p.endpoints),
      mapping: asString(p.mapping),
      resources: asString(p.resources),
      transforms: asString(p.transforms),
    });
    setDescTab(lang);
  };

  const save = async () => {
    const endpoints = parseJson(form.endpoints);
    const mapping = parseJson(form.mapping);
    const resources = parseJson(form.resources);
    const transforms = parseJson(form.transforms);
    if (endpoints === null || mapping === null || resources === null || transforms === null) {
      setError(t("admin.providersConfigInvalid"));
      return;
    }
    const descriptions: Record<string, string> = {};
    for (const code of LANG_CODES) {
      if (form.descriptions[code]?.trim()) descriptions[code] = form.descriptions[code].trim();
    }
    setSaving(true);
    try {
      await apiClient.upsertOpProvider({
        provider_id: form.provider_id.trim(),
        name: form.name.trim(),
        base_url: form.base_url.trim() || null,
        wired: form.wired,
        description: descriptions,
        endpoints,
        mapping,
        resources,
        transforms,
      });
      setError(null);
      startNew();
      await load();
    } catch {
      setError(t("admin.providersSaveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (p: OpProvider) => {
    if (!window.confirm(`${t("admin.providersDeleteConfirm")} ${p.provider_id}?`)) return;
    try {
      await apiClient.deleteOpProvider(p.provider_id);
      await load();
    } catch {
      setError(t("admin.providersDeleteFailed"));
    }
  };

  const toggleWired = async (p: OpProvider, wired: boolean) => {
    try {
      await apiClient.setOpProviderWired(p.provider_id, wired);
      await load();
    } catch {
      setError(t("admin.providersSaveFailed"));
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("admin.providersTitle")}</h1>
        <button
          onClick={startNew}
          className="rounded bg-osap-accent px-4 py-1.5 text-sm text-white"
        >
          + {t("admin.providersNew")}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {viewing !== null || editing !== null || items.length === 0 ? (
        <Card
          title={
            viewing !== null
              ? `${t("admin.providersView")} · ${viewing}`
              : editing === null
                ? t("admin.providersNew")
                : `${t("admin.providersEdit")} · ${editing}`
          }
        >
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="text-xs text-osap-muted">
              provider_id
              <input
                value={form.provider_id}
                onChange={(e) => setForm({ ...form, provider_id: e.target.value })}
                placeholder="provider_id"
                disabled={editing !== null || viewing !== null}
                className="mt-1 w-full rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("admin.providersName")}
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={viewing !== null}
                className="mt-1 w-full rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted sm:col-span-2">
              base_url
              <input
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                disabled={viewing !== null}
                className="mt-1 w-full rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-osap-muted" title={t("admin.providersConnectHint")}>
              <input
                type="checkbox"
                checked={form.wired}
                onChange={(e) => setForm({ ...form, wired: e.target.checked })}
                disabled={viewing !== null}
                className="h-4 w-4"
              />
              {t("admin.providersConnect")}
            </label>
          </div>

          <div className="mt-3">
            <p className="text-xs font-semibold text-osap-muted">{t("admin.providersDescription")}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {LANG_CODES.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => setDescTab(code)}
                  className={`rounded px-2 py-0.5 text-xs ${
                    descTab === code
                      ? "bg-osap-accent text-white"
                      : "border border-osap-border text-osap-muted hover:bg-osap-surface"
                  }`}
                >
                  {code.toUpperCase()}
                </button>
              ))}
            </div>
            <textarea
              value={form.descriptions[descTab] ?? ""}
              onChange={(e) =>
                setForm({ ...form, descriptions: { ...form.descriptions, [descTab]: e.target.value } })
              }
              disabled={viewing !== null}
              placeholder={t("admin.providersDescription")}
              className="mt-2 min-h-20 w-full rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
            />
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {(
              [
                ["endpoints", form.endpoints],
                ["mapping", form.mapping],
                ["resources", form.resources],
                ["transforms", form.transforms],
              ] as const
            ).map(([key, value]) => (
              <label key={key} className="text-xs text-osap-muted">
                {key} (JSON)
                <textarea
                  value={value}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  disabled={viewing !== null}
                  className="mt-1 min-h-28 w-full rounded border border-osap-border bg-osap-surface p-2 font-mono text-xs"
                />
              </label>
            ))}
          </div>

          <div className="mt-3 flex gap-2">
            {viewing === null ? (
              <button
                onClick={() => void save()}
                disabled={saving}
                className="rounded bg-osap-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {t("admin.providersSave")}
              </button>
            ) : null}
            <button
              onClick={startNew}
              className="rounded border border-osap-border px-4 py-1.5 text-sm text-osap-muted"
            >
              {t("admin.providersCancel")}
            </button>
          </div>
        </Card>
      ) : null}

      {items.length === 0 && editing === null && (
        <p className="text-sm text-osap-muted">{t("states.empty")}</p>
      )}

      {viewing === null && editing === null && items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-osap-border text-left text-xs text-osap-muted">
                <th className="px-2 py-2">{t("admin.providersProvider")}</th>
                <th className="px-2 py-2">{t("admin.providersDescription")}</th>
                <th className="px-2 py-2">base_url</th>
                <th className="px-2 py-2">{t("admin.providersState")}</th>
                <th className="px-2 py-2 text-right">{t("admin.providersActions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.provider_id} className="border-b border-osap-border">
                  <td className="px-2 py-2">
                    <div className="font-medium">{p.name}</div>
                    <div className="font-mono text-xs text-osap-muted">{p.provider_id}</div>
                  </td>
                  <td className="px-2 py-2 text-osap-muted">{desc(p) || "—"}</td>
                  <td className="px-2 py-2 font-mono text-xs">{p.base_url || "—"}</td>
                  <td className="px-2 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        p.wired
                          ? "bg-osap-success/20 text-osap-success"
                          : "bg-osap-danger/20 text-osap-danger"
                      }`}
                    >
                      {p.wired ? t("providers.online") : t("providers.offline")}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-right">
                    <div className="flex justify-end gap-1.5">
                      <IconButton
                        title={t("admin.providersView")}
                        onClick={() => startView(p)}
                        path="M2.5 12S5.5 5.5 12 5.5 21.5 12 21.5 12 18.5 18.5 12 18.5 2.5 12 2.5 12z M12 15a3 3 0 100-6 3 3 0 000 6z"
                      />
                      <IconButton
                        title={t("admin.providersEdit")}
                        onClick={() => startEdit(p)}
                        path="M12 20h9 M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"
                      />
                      <IconButton
                        title={p.wired ? t("admin.providersDisconnect") : t("admin.providersConnect")}
                        onClick={() => toggleWired(p, !p.wired)}
                        path="M5 12h14 M13 6l6 6-6 6"
                      />
                      <IconButton
                        title={t("admin.providersDelete")}
                        danger
                        onClick={() => void remove(p)}
                        path="M3 6h18 M8 6V4h8v2 M19 6l-1 14H6L5 6 M10 11v6 M14 11v6"
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function IconButton({
  title,
  onClick,
  path,
  danger = false,
}: {
  title: string;
  onClick: () => void;
  path: string;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`rounded p-1 transition-colors ${
        danger
          ? "text-osap-danger hover:bg-osap-danger/10"
          : "text-osap-muted hover:bg-osap-surface hover:text-osap-accent"
      }`}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={path} />
      </svg>
    </button>
  );
}
