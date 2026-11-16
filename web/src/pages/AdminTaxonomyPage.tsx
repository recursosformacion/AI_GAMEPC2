import { useEffect, useState } from "react";

import { apiClient } from "../api/ApiClient";
import type { Taxonomy, TaxonomyRole, TaxonomySection, TaxonomyType } from "../api/types";
import { Card } from "../components/Card";

const EMPTY: Taxonomy = { types: [], roles: [], sections: [] };

export function AdminTaxonomyPage() {
  const [data, setData] = useState<Taxonomy>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient
      .getAmigosTaxonomy()
      .then(setData)
      .catch(() => setError("No se pudo cargar la taxonomía."))
      .finally(() => setLoading(false));
  }, []);

  const updateType = (index: number, field: keyof TaxonomyType, value: string) => {
    setData((current) => ({
      ...current,
      types: current.types.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    }));
  };

  const updateRole = (index: number, field: keyof TaxonomyRole, value: string) => {
    setData((current) => ({
      ...current,
      roles: current.roles.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    }));
  };

  const updateSection = (index: number, field: keyof TaxonomySection, value: string) => {
    setData((current) => ({
      ...current,
      sections: current.sections.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    }));
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      setData(await apiClient.saveAmigosTaxonomy(data));
      setMessage("Taxonomía guardada.");
    } catch {
      setError("No se pudo guardar la taxonomía.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="text-sm text-osap-muted">Cargando…</p>;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2 border-b border-osap-border pb-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
            Administración
          </p>
          <h1 className="text-2xl font-semibold text-osap-ink">Taxonomías de grupos</h1>
          <p className="mt-1 text-sm text-osap-muted">
            Tipos y subtipos, cargos administrativos, roles musicales y secciones.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="rounded bg-osap-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Guardar taxonomía
        </button>
      </header>
      {error && <p className="text-sm text-red-500">{error}</p>}
      {message && <p className="text-sm text-emerald-600">{message}</p>}

      <Card title="Tipos y subtipos">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-osap-muted">
              <th className="p-1">Código</th><th className="p-1">Padre</th>
              <th className="p-1">Nombre</th><th className="p-1">Kind</th><th />
            </tr></thead>
            <tbody>
              {data.types.map((row, index) => (
                <tr key={`${row.code}-${index}`} className="border-t border-osap-border">
                  <td className="p-1"><input value={row.code} onChange={(e) => updateType(index, "code", e.target.value)} className="w-32 rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                  <td className="p-1"><select value={row.parent_code ?? ""} onChange={(e) => updateType(index, "parent_code", e.target.value)} className="w-32 rounded border border-osap-border bg-osap-surface px-2 py-1"><option value="">—</option>{data.types.map((t) => <option key={t.code} value={t.code}>{t.code}</option>)}</select></td>
                  <td className="p-1"><input value={row.name} onChange={(e) => updateType(index, "name", e.target.value)} className="w-full rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                  <td className="p-1"><input value={row.kind} onChange={(e) => updateType(index, "kind", e.target.value)} className="w-24 rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                  <td className="p-1"><button type="button" className="text-osap-danger" onClick={() => setData((c) => ({ ...c, types: c.types.filter((_, i) => i !== index) }))}>Quitar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" className="mt-2 text-sm text-osap-accent" onClick={() => setData((c) => ({ ...c, types: [...c.types, { code: "nuevo", parent_code: null, name: "Nuevo tipo", kind: "grupo" }] }))}>+ Añadir tipo</button>
      </Card>

      <Card title="Cargos y roles">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-osap-muted"><th className="p-1">Tipo</th><th className="p-1">Ámbito</th><th className="p-1">Código</th><th className="p-1">Nombre</th><th /></tr></thead>
          <tbody>
            {data.roles.map((row, index) => (
              <tr key={`${row.type_code}-${row.code}-${index}`} className="border-t border-osap-border">
                <td className="p-1"><select value={row.type_code} onChange={(e) => updateRole(index, "type_code", e.target.value)} className="rounded border border-osap-border bg-osap-surface px-2 py-1">{data.types.map((t) => <option key={t.code} value={t.code}>{t.code}</option>)}</select></td>
                <td className="p-1"><select value={row.scope} onChange={(e) => updateRole(index, "scope", e.target.value)} className="rounded border border-osap-border bg-osap-surface px-2 py-1"><option value="admin">Administrativo</option><option value="musical">Musical</option></select></td>
                <td className="p-1"><input value={row.code} onChange={(e) => updateRole(index, "code", e.target.value)} className="w-32 rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                <td className="p-1"><input value={row.name} onChange={(e) => updateRole(index, "name", e.target.value)} className="w-full rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                <td className="p-1"><button type="button" className="text-osap-danger" onClick={() => setData((c) => ({ ...c, roles: c.roles.filter((_, i) => i !== index) }))}>Quitar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="mt-2 text-sm text-osap-accent" onClick={() => setData((c) => ({ ...c, roles: [...c.roles, { type_code: c.types[0]?.code ?? "", scope: "admin", code: "nuevo", name: "Nuevo cargo" }] }))}>+ Añadir cargo/rol</button>
      </Card>

      <Card title="Secciones y cuerdas">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-osap-muted"><th className="p-1">Tipo</th><th className="p-1">Código</th><th className="p-1">Nombre</th><th /></tr></thead>
          <tbody>
            {data.sections.map((row, index) => (
              <tr key={`${row.type_code}-${row.code}-${index}`} className="border-t border-osap-border">
                <td className="p-1"><select value={row.type_code} onChange={(e) => updateSection(index, "type_code", e.target.value)} className="rounded border border-osap-border bg-osap-surface px-2 py-1">{data.types.map((t) => <option key={t.code} value={t.code}>{t.code}</option>)}</select></td>
                <td className="p-1"><input value={row.code} onChange={(e) => updateSection(index, "code", e.target.value)} className="w-32 rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                <td className="p-1"><input value={row.name} onChange={(e) => updateSection(index, "name", e.target.value)} className="w-full rounded border border-osap-border bg-osap-surface px-2 py-1" /></td>
                <td className="p-1"><button type="button" className="text-osap-danger" onClick={() => setData((c) => ({ ...c, sections: c.sections.filter((_, i) => i !== index) }))}>Quitar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="mt-2 text-sm text-osap-accent" onClick={() => setData((c) => ({ ...c, sections: [...c.sections, { type_code: c.types[0]?.code ?? "", code: "nueva", name: "Nueva sección" }] }))}>+ Añadir sección</button>
      </Card>
    </div>
  );
}
