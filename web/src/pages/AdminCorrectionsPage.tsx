import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { CorrectionRequestRead } from "../api/types";
import { Spinner } from "../components/Spinner";

export function AdminCorrectionsPage() {
  const [items, setItems] = useState<CorrectionRequestRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await apiClient.listCorrections());
      setError(null);
    } catch {
      setError("No se pudieron cargar las solicitudes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const resolve = async (id: string, action: "review" | "close") => {
    setBusyId(id);
    try {
      await apiClient.resolveCorrection(id, action, "");
      await load();
    } catch {
      setError("No se pudo resolver la solicitud.");
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <Spinner />;
  return (
    <div className="mx-auto max-w-4xl space-y-4 px-4 py-8">
      <h1 className="text-2xl font-semibold">Solicitudes (contacto / correcciones)</h1>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {items.length === 0 && <p className="text-osap-muted">Sin solicitudes pendientes.</p>}
      <ul className="divide-y divide-osap-border rounded-lg border border-osap-border bg-white">
        {items.map((c) => (
          <li key={c.id} className="px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm">
                <span className="font-medium">{c.kind}</span>
                {c.entity_id ? (
                  <span className="ml-2 text-osap-muted">· {c.entity_id}{c.field ? ` (${c.field})` : ""}</span>
                ) : null}
                <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${c.status === "pending" ? "bg-amber-100" : "bg-emerald-100"}`}>
                  {c.status}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-osap-muted">{c.id}</span>
                {c.status === "pending" && (
                  <>
                    <button
                      type="button"
                      disabled={busyId === c.id}
                      onClick={() => void resolve(c.id, "review")}
                      className="rounded border border-osap-border px-2 py-1 text-xs hover:bg-osap-surface"
                    >
                      Revisada
                    </button>
                    <button
                      type="button"
                      disabled={busyId === c.id}
                      onClick={() => void resolve(c.id, "close")}
                      className="rounded border border-osap-border px-2 py-1 text-xs hover:bg-osap-surface"
                    >
                      Cerrar
                    </button>
                  </>
                )}
              </div>
            </div>
            <p className="mt-1 text-sm">{c.message}</p>
            {c.proposed_value ? (
              <p className="text-sm text-osap-muted">Propuesta: {c.proposed_value}</p>
            ) : null}
            <p className="mt-1 text-xs text-osap-muted">
              Solicitante: {c.requested_by_name || c.requested_by_email || c.requested_by || "—"} ·{" "}
              {c.created_at}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
