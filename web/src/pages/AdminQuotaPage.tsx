// Admin · Cuotas de descarga OMR y estadísticas (download_usage).
// Planes (visitor/registered/donor), excepciones por usuario con vigencia y resumen de uso.

import { useCallback, useEffect, useState } from "react";
import {
  apiClient,
  type QuotaOverride,
  type QuotaPlan,
  type QuotaUsage,
} from "../api/ApiClient";

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function AdminQuotaPage() {
  const [plans, setPlans] = useState<QuotaPlan[]>([]);
  const [overrides, setOverrides] = useState<QuotaOverride[]>([]);
  const [usage, setUsage] = useState<QuotaUsage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({ user_id: "", limit: "", from: "", until: "", note: "" });

  const load = useCallback(async () => {
    setError("");
    const today = new Date();
    const from = new Date(today);
    from.setDate(from.getDate() - 29);
    try {
      const [p, o, u] = await Promise.all([
        apiClient.getQuotaPlans(),
        apiClient.getQuotaOverrides(),
        apiClient.getQuotaUsage(isoDay(from), isoDay(today)),
      ]);
      setPlans(p);
      setOverrides(o);
      setUsage(u);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function savePlan(name: string, limit: number) {
    setBusy(true);
    try {
      await apiClient.setQuotaPlan(name, { downloads_per_day: limit });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el plan");
    } finally {
      setBusy(false);
    }
  }

  async function saveOverride() {
    if (!draft.user_id.trim() || draft.limit === "") return;
    setBusy(true);
    try {
      await apiClient.setQuotaOverride(draft.user_id.trim(), {
        downloads_per_day: Number(draft.limit),
        valid_from: draft.from || null,
        valid_until: draft.until || null,
        note: draft.note || null,
      });
      setDraft({ user_id: "", limit: "", from: "", until: "", note: "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar la excepción");
    } finally {
      setBusy(false);
    }
  }

  async function removeOverride(userId: string) {
    setBusy(true);
    try {
      await apiClient.deleteQuotaOverride(userId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo borrar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-bold">Cuotas de descarga OMR</h1>
      {error && <p className="alert alert--error text-red-600">{error}</p>}

      <div>
        <h2 className="mb-2 text-base font-semibold">Planes</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-osap-muted">
              <th className="py-1">Plan</th>
              <th>Límite/día</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {plans.map((p) => (
              <PlanRow key={p.name} plan={p} busy={busy} onSave={savePlan} />
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="mb-2 text-base font-semibold">Excepciones por usuario</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-osap-muted">
              <th className="py-1">Usuario</th>
              <th>Límite</th>
              <th>Desde</th>
              <th>Hasta</th>
              <th>Nota</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {overrides.map((o) => (
              <tr key={o.user_id} className="border-t border-osap-border">
                <td className="py-1">{o.user_id}</td>
                <td>{o.downloads_per_day}</td>
                <td>{o.valid_from ?? "—"}</td>
                <td>{o.valid_until ?? "—"}</td>
                <td>{o.note ?? "—"}</td>
                <td>
                  <button
                    type="button"
                    className="text-red-600 hover:underline"
                    disabled={busy}
                    onClick={() => void removeOverride(o.user_id)}
                  >
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
            <tr className="border-t border-osap-border">
              <td className="py-1">
                <input
                  className="w-full rounded border border-osap-border px-2 py-1"
                  placeholder="user_id"
                  value={draft.user_id}
                  onChange={(e) => setDraft({ ...draft, user_id: e.target.value })}
                />
              </td>
              <td>
                <input
                  className="w-20 rounded border border-osap-border px-2 py-1"
                  type="number"
                  placeholder="100"
                  value={draft.limit}
                  onChange={(e) => setDraft({ ...draft, limit: e.target.value })}
                />
              </td>
              <td>
                <input
                  className="rounded border border-osap-border px-2 py-1"
                  type="date"
                  value={draft.from}
                  onChange={(e) => setDraft({ ...draft, from: e.target.value })}
                />
              </td>
              <td>
                <input
                  className="rounded border border-osap-border px-2 py-1"
                  type="date"
                  value={draft.until}
                  onChange={(e) => setDraft({ ...draft, until: e.target.value })}
                />
              </td>
              <td>
                <input
                  className="w-full rounded border border-osap-border px-2 py-1"
                  placeholder="nota"
                  value={draft.note}
                  onChange={(e) => setDraft({ ...draft, note: e.target.value })}
                />
              </td>
              <td>
                <button
                  type="button"
                  className="rounded bg-osap-accent px-3 py-1 text-white disabled:opacity-50"
                  disabled={busy || !draft.user_id || draft.limit === ""}
                  onClick={() => void saveOverride()}
                >
                  Añadir
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="mb-2 text-base font-semibold">Estadísticas (últimos 30 días)</h2>
        {!usage ? (
          <p className="text-sm text-osap-muted">Sin datos.</p>
        ) : (
          <div className="space-y-3 text-sm">
            <p>
              <strong>{usage.total}</strong> descargas facturables · {usage.registered} registradas ·{" "}
              {usage.anonymous} anónimas · {usage.distinct_users} usuarios · {usage.distinct_ips} IPs
            </p>
            <div>
              <h3 className="font-medium">Por proveedor</h3>
              <ul className="list-disc pl-5">
                {usage.by_provider.map((r) => (
                  <li key={r.provider}>
                    {r.provider}: {r.total}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-medium">Obras más descargadas</h3>
              <ul className="list-disc pl-5">
                {usage.top_works.slice(0, 10).map((r) => (
                  <li key={r.work_id}>
                    obra {r.work_id}: {r.total}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-medium">Por día</h3>
              <ul className="list-disc pl-5">
                {usage.by_day.map((r) => (
                  <li key={r.day}>
                    {r.day}: {r.total}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function PlanRow({
  plan,
  busy,
  onSave,
}: {
  plan: QuotaPlan;
  busy: boolean;
  onSave: (name: string, limit: number) => Promise<void>;
}) {
  const [value, setValue] = useState(String(plan.downloads_per_day));
  return (
    <tr className="border-t border-osap-border">
      <td className="py-1">{plan.name}</td>
      <td>
        <input
          className="w-24 rounded border border-osap-border px-2 py-1"
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </td>
      <td>
        <button
          type="button"
          className="rounded border border-osap-border px-3 py-1 disabled:opacity-50"
          disabled={busy || value === "" || Number(value) === plan.downloads_per_day}
          onClick={() => void onSave(plan.name, Number(value))}
        >
          Guardar
        </button>
      </td>
    </tr>
  );
}
