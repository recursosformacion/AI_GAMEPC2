// Revisión humana de las propuestas de atribución de la IA (Gemini) sobre una obra.
//
// La SPA NO contiene lógica de IA: consume los endpoints de osap-api, que delega en
// osap-storage. Aceptar una propuesta es lo único que asigna la persona (vía canónica de
// storage, con su auditoría). Las pestañas filtran por estado; el detalle muestra la
// evidencia y la respuesta del modelo tal cual las devuelve el backend.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { WorkAiProposal, WorkAiProposalStatus, WorkAiReviewAction } from "../api/types";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";

const TABS: { key: WorkAiProposalStatus; label: string }[] = [
  { key: "pending", label: "Pendientes" },
  { key: "accepted", label: "Aceptadas" },
  { key: "rejected", label: "Rechazadas" },
  { key: "uncertain", label: "Dudosas" },
];

const RESOLUTION_LABEL: Record<string, string> = {
  identified: "Autor identificado",
  anonymous: "Anónima",
  traditional: "Tradicional",
  unknown: "Sin evidencia suficiente",
};

const MATCH_LABEL: Record<string, string> = {
  matched: "Persona encontrada",
  ambiguous: "Varias personas posibles",
  unresolved: "Persona no encontrada",
  not_applicable: "No aplica",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  accepted: "Aceptada",
  rejected: "Rechazada",
  uncertain: "Dudosa",
};

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-900",
  accepted: "bg-emerald-100 text-emerald-900",
  rejected: "bg-red-100 text-red-900",
  uncertain: "bg-slate-200 text-slate-800",
};

function evidenceTexts(raw: string | null | undefined): string[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) =>
        typeof item === "object" && item !== null
          ? [String((item as Record<string, unknown>).type ?? ""), String((item as Record<string, unknown>).text ?? "")]
              .filter(Boolean)
              .join(": ")
          : String(item),
      )
      .filter(Boolean);
  } catch {
    return [];
  }
}

function safeJson(raw: string | null | undefined): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export function AdminWorkPersonAiPage() {
  const [status, setStatus] = useState<WorkAiProposalStatus>("pending");
  const [items, setItems] = useState<WorkAiProposal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<WorkAiProposal | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await apiClient.listWorkAttributionProposals(status, 50, 0);
      setItems(page.items);
      setTotal(page.total);
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.code === "AI_NOT_CONFIGURED"
          ? "IA no configurada en storage (falta la API key)."
          : "No se pudieron cargar las propuestas.",
      );
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  const review = async (proposal: WorkAiProposal, action: WorkAiReviewAction) => {
    setBusyId(proposal.id);
    try {
      await apiClient.reviewWorkAttributionProposal(proposal.id, action);
      await load();
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === "PROPOSAL_NOT_ASSIGNABLE") {
        setError("No se puede aceptar: la persona de la propuesta no está resuelta (match exacto).");
      } else if (cause instanceof ApiError && cause.code === "AI_NOT_CONFIGURED") {
        setError("IA no configurada en storage (falta la API key).");
      } else {
        setError("No se pudo registrar la revisión.");
      }
    } finally {
      setBusyId(null);
    }
  };

  const toggleDetail = async (proposal: WorkAiProposal) => {
    if (openId === proposal.id) {
      setOpenId(null);
      setDetail(null);
      return;
    }
    setOpenId(proposal.id);
    setDetail(null);
    try {
      setDetail(await apiClient.getWorkAttributionProposal(proposal.id));
    } catch {
      setError("No se pudo cargar el detalle de la propuesta.");
    }
  };

  const openWorkPersons = async () => {
    try {
      const r = await apiClient.getStorageWebUrl("work-persons");
      window.open(r.url, "_blank");
    } catch {
      setError("El mantenimiento de storage no está disponible.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Atribución IA (revisión humana)</h1>
        <button
          type="button"
          onClick={() => void openWorkPersons()}
          className="rounded border border-osap-border px-3 py-1.5 text-sm hover:bg-osap-surface"
        >
          Obras → Personas
        </button>
      </div>
      <p className="text-sm text-osap-muted">
        La IA solo propone. Aceptar una propuesta asigna la persona en el catálogo y queda auditado;
        rechazar o marcar dudosa no modifica nada.
      </p>

      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setStatus(tab.key)}
            className={`rounded px-3 py-1.5 text-sm ${
              status === tab.key
                ? "bg-osap-accent text-white"
                : "border border-osap-border text-osap-muted hover:bg-osap-surface"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <span className="ml-2 self-center text-xs text-osap-muted">{total} propuestas</span>
      </div>

      {error && <p className="text-sm text-red-700">{error}</p>}
      {loading && <Spinner />}
      {!loading && items.length === 0 && <p className="text-sm text-osap-muted">Sin propuestas en este estado.</p>}

      {items.map((p) => (
        <Card key={p.id} title={`Obra #${p.work_id} · propuesta ${p.id}`}>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className={`rounded-full px-2 py-0.5 ${STATUS_CLASS[p.status] ?? "bg-slate-200"}`}>
              {STATUS_LABEL[p.status] ?? p.status}
            </span>
            <span className="rounded bg-osap-accent-soft px-2 py-0.5">
              {RESOLUTION_LABEL[p.resolution] ?? p.resolution}
            </span>
            <span className="rounded bg-osap-accent-soft px-2 py-0.5">
              {MATCH_LABEL[p.person_match] ?? p.person_match}
            </span>
            {typeof p.confidence === "number" && (
              <span className="text-osap-muted">confianza {p.confidence.toFixed(2)}</span>
            )}
            {p.model && <span className="text-osap-muted">modelo {p.model}</span>}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
            <Link to={`/obra/${p.work_id}`} className="text-osap-accent hover:underline">
              Obra #{p.work_id}
            </Link>
            {p.candidate_person_id ? (
              <Link
                to={`/composers/${encodeURIComponent(p.candidate_person_id)}`}
                className="text-osap-accent hover:underline"
              >
                Persona: {p.candidate_name ?? p.candidate_person_id}
              </Link>
            ) : (
              <span className="text-osap-muted">Sin persona propuesta</span>
            )}
            {p.role_name && <span className="text-osap-muted">rol: {p.role_name}</span>}
          </div>

          {evidenceTexts(p.evidence_json).length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-osap-muted">
              {evidenceTexts(p.evidence_json).map((line, i) => (
                <li key={i}>· {line}</li>
              ))}
            </ul>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void review(p, "accept")}
              disabled={busyId === p.id}
              className="rounded bg-green-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Aceptar
            </button>
            <button
              type="button"
              onClick={() => void review(p, "reject")}
              disabled={busyId === p.id}
              className="rounded bg-red-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Rechazar
            </button>
            <button
              type="button"
              onClick={() => void review(p, "uncertain")}
              disabled={busyId === p.id}
              className="rounded border border-osap-border px-3 py-1.5 text-sm hover:bg-osap-surface disabled:opacity-50"
            >
              Marcar dudosa
            </button>
            <button
              type="button"
              onClick={() => void toggleDetail(p)}
              className="rounded border border-osap-border px-3 py-1.5 text-sm hover:bg-osap-surface"
            >
              {openId === p.id ? "Ocultar detalle" : "Ver detalle"}
            </button>
            {p.reviewed_by && (
              <span className="text-xs text-osap-muted">
                revisada por {p.reviewed_by}
                {p.review_note ? ` · ${p.review_note}` : ""}
              </span>
            )}
          </div>

          {openId === p.id && (
            <div className="mt-3 rounded border border-osap-border bg-osap-bg p-3 text-xs">
              <p className="text-osap-muted">
                prompt: {p.prompt_version ?? "—"} · created_at: {p.created_at ?? "—"}
              </p>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">
                {detail
                  ? JSON.stringify(
                      {
                        answer: safeJson(detail.answer_json),
                        evidence: evidenceTexts(detail.evidence_json),
                      },
                      null,
                      2,
                    )
                  : "Cargando detalle…"}
              </pre>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
