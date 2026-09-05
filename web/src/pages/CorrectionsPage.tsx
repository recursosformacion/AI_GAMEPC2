import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { CorrectionRequestRead } from "../api/types";
import { Button } from "../components/Button";

type Kind = "contact" | "source" | "composer" | "work";

const KIND_LABEL: Record<Kind, string> = {
  contact: "Contacto",
  source: "Fuente / proveedor",
  composer: "Compositor",
  work: "Obra",
};

export function CorrectionsPage() {
  const [params] = useSearchParams();
  const initialKind = params.get("kind") === "contact" ? "contact" : (params.get("kind") as Kind) || "contact";
  const [kind, setKind] = useState<Kind>(initialKind);
  const [entityId, setEntityId] = useState(params.get("entity_id") || "");
  const [field, setField] = useState(params.get("field") || "");
  const [currentValue, setCurrentValue] = useState(params.get("current_value") || "");
  const [proposedValue, setProposedValue] = useState("");
  const [message, setMessage] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [result, setResult] = useState<CorrectionRequestRead | null>(null);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!message.trim()) {
      setError("Escribe un mensaje.");
      setStatus("error");
      return;
    }
    if (kind !== "contact" && !entityId.trim()) {
      setError("Indica la entidad (fuente/compositor/obra).");
      setStatus("error");
      return;
    }
    setStatus("sending");
    setError("");
    try {
      const created =
        kind === "contact"
          ? await apiClient.submitContact(message, contactEmail || undefined)
          : await apiClient.submitCorrection({
              kind: kind as "source" | "composer" | "work",
              entity_id: entityId.trim(),
              entity_provider: kind === "work" ? "omr" : undefined,
              field: kind === "work" ? "title" : field.trim() || undefined,
              current_value: currentValue || undefined,
              proposed_value: proposedValue || undefined,
              message,
            });
      setResult(created);
      setStatus("sent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo enviar la solicitud.");
      setStatus("error");
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <Link to="/" className="text-sm text-osap-accent hover:underline">
        ← Volver
      </Link>
      <header>
        <h1 className="text-2xl font-semibold">Contacto y correcciones</h1>
        <p className="mt-2 text-sm text-osap-muted">
          Contacta con el proyecto o propón una corrección de datos del catálogo. Las
          correcciones quedan <em>pendientes de revisión</em>: no modifican el catálogo automáticamente.
        </p>
      </header>

      <section className="space-y-4 rounded-lg border border-osap-border bg-white p-5">
        <div className="flex flex-wrap gap-2">
          {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={`rounded-full border px-3 py-1 text-sm ${
                kind === k ? "border-osap-accent bg-osap-accent text-white" : "border-osap-border text-osap-muted"
              }`}
            >
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>

        {kind !== "contact" && entityId ? (
          <div className="rounded border border-osap-border bg-osap-surface p-3 text-sm">
            <p className="font-medium">
              Objeto de la solicitud: {KIND_LABEL[kind]} · {entityId}
            </p>
            {currentValue ? (
              <p className="mt-1 text-osap-muted">Valor actual: {currentValue}</p>
            ) : null}
          </div>
        ) : null}

        {kind !== "contact" && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              ID de la entidad
              <input
                value={entityId}
                onChange={(e) => setEntityId(e.target.value)}
                placeholder={kind === "source" ? "p. ej. imslp, omr" : "id"}
                className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
              />
            </label>
            {kind === "work" ? (
              <>
                <div className="block text-sm text-osap-muted">Origen: OMR (OSAP-storage)</div>
                <div className="block text-sm text-osap-muted">Corrección permitida: título de la obra</div>
              </>
            ) : (
              <label className="block text-sm">
                Campo afectado
                <input
                  value={field}
                  onChange={(e) => setField(e.target.value)}
                  placeholder={kind === "source" ? "description" : "name"}
                  className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
                />
              </label>
            )}
            <label className="block text-sm">
              Valor actual
              <input
                value={currentValue}
                onChange={(e) => setCurrentValue(e.target.value)}
                className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              Valor propuesto
              <input
                value={proposedValue}
                onChange={(e) => setProposedValue(e.target.value)}
                className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
              />
            </label>
          </div>
        )}

        {kind === "contact" && (
          <label className="block text-sm">
            Tu correo (opcional)
            <input
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
            />
          </label>
        )}

        <label className="block text-sm">
          Mensaje
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
          />
        </label>

        {status === "error" && <p className="text-sm text-red-700">{error}</p>}
        {status === "sent" && result && (
          <p className="rounded border border-osap-border bg-osap-surface px-3 py-2 text-sm">
            Solicitud enviada. Referencia: {result.id} (estado: {result.status})
          </p>
        )}

        <Button onClick={() => void submit()} disabled={status === "sending"}>
          {status === "sending" ? "Enviando…" : "Enviar solicitud"}
        </Button>
      </section>
    </div>
  );
}
