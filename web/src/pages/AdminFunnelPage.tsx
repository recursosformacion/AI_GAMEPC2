// Admin · Funnel S0–S4. Solo visualiza FunnelMetricsResponse (funnel_events + download_usage).

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { FunnelEventCounts, FunnelMetrics } from "../api/types";

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const EVENT_ROWS: { key: keyof FunnelEventCounts; label: string }[] = [
  { key: "anon_limit_reached", label: "Límite anónimo (S1)" },
  { key: "registered", label: "Registro (S2)" },
  { key: "user_limit_reached", label: "Límite usuario (S3)" },
  { key: "membership_activated", label: "Membresía activada (S4)" },
  { key: "membership_lapsed", label: "Membresía caducada" },
  { key: "promotion_applied", label: "Promoción aplicada" },
  { key: "promotion_reverted", label: "Promoción revocada" },
];

export function AdminFunnelPage() {
  const [from, setFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 29);
    return isoDay(d);
  });
  const [to, setTo] = useState(() => isoDay(new Date()));
  const [data, setData] = useState<FunnelMetrics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (start: string, end: string) => {
    setLoading(true);
    setError("");
    try {
      setData(await apiClient.getFunnelMetrics(start, end));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(from, to);
  }, [load, from, to]);

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Funnel S0–S4</h1>
        <p className="mt-1 text-sm text-osap-muted">
          Eventos, usuarios únicos, conversiones y descargas (fuente: <code>funnel_events</code> +{" "}
          <code>download_usage</code>).
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Desde
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="ml-2 rounded border border-osap-border bg-osap-surface px-2 py-1"
          />
        </label>
        <label className="text-sm">
          Hasta
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="ml-2 rounded border border-osap-border bg-osap-surface px-2 py-1"
          />
        </label>
        <button
          type="button"
          onClick={() => void load(from, to)}
          disabled={loading}
          className="rounded border border-osap-border px-3 py-1.5 text-sm hover:bg-osap-bg"
        >
          {loading ? "Cargando…" : "Actualizar"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-osap-border bg-osap-surface p-4">
            <h2 className="text-sm font-medium text-osap-muted">Periodo</h2>
            <p className="mt-1 text-sm">
              {data.period.from_day} → {data.period.to_day}
            </p>
          </div>

          <div className="rounded-lg border border-osap-border bg-osap-surface p-4">
            <h2 className="text-sm font-medium text-osap-muted">Conversiones</h2>
            <p className="mt-1 text-sm">Anónimo → usuario: {data.conversions.anon_to_user}</p>
            <p className="text-sm">Usuario → donor: {data.conversions.user_to_donor}</p>
          </div>

          <div className="rounded-lg border border-osap-border bg-osap-surface p-4 lg:col-span-2">
            <h2 className="text-sm font-medium text-osap-muted">Eventos por etapa</h2>
            <table className="mt-2 w-full text-sm">
              <thead>
                <tr className="text-left text-osap-muted">
                  <th>Evento</th>
                  <th>Eventos</th>
                  <th>Usuarios</th>
                </tr>
              </thead>
              <tbody>
                {EVENT_ROWS.map(({ key, label }) => (
                  <tr key={key as string} className="border-t border-osap-border">
                    <td className="py-1">{label}</td>
                    <td className="py-1">{data.events[key]}</td>
                    <td className="py-1">{data.users[key]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="rounded-lg border border-osap-border bg-osap-surface p-4 lg:col-span-2">
            <h2 className="text-sm font-medium text-osap-muted">Descargas</h2>
            <p className="mt-1 text-sm">
              Total: {data.downloads.total} · anónimas: {data.downloads.anonymous} · registradas:{" "}
              {data.downloads.registered}
            </p>
            {data.downloads.by_provider.length > 0 && (
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="text-left text-osap-muted">
                    <th>Proveedor</th>
                    <th>Descargas</th>
                  </tr>
                </thead>
                <tbody>
                  {data.downloads.by_provider.map((p) => (
                    <tr key={p.provider} className="border-t border-osap-border">
                      <td className="py-1">{p.provider}</td>
                      <td className="py-1">{p.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
