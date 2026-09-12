import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { CorrectionRequestRead } from "../api/types";
import { Button } from "../components/Button";

type Kind = "contact" | "source" | "composer" | "work" | "representation";

const KIND_LABEL: Record<Kind, string> = {
  contact: "Contacto",
  source: "Fuente / proveedor",
  composer: "Compositor",
  work: "Obra",
  representation: "Representación",
};

export function CorrectionsPage() {
  const [params] = useSearchParams();
  // La entidad llega oculta en la URL al pulsar "Sugerir una modificación": no se
  // muestra ni se edita aquí; solo se asocia a la solicitud.
  const arrivedKind = params.get("kind") as Kind | null;
  const initialKind: Kind =
    arrivedKind === "source" ||
    arrivedKind === "composer" ||
    arrivedKind === "work" ||
    arrivedKind === "representation" ||
    arrivedKind === "contact"
      ? arrivedKind
      : "contact";
  const arrivedEntity = params.get("entity_id") || "";
  const [kind, setKind] = useState<Kind>(initialKind);
  const entityId = kind === arrivedKind ? arrivedEntity : "";
  const [message, setMessage] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [result, setResult] = useState<CorrectionRequestRead | null>(null);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!message.trim()) {
      setError("Escribe un mensaje con la corrección que propones.");
      setStatus("error");
      return;
    }
    if (kind !== "contact" && !entityId.trim()) {
      setError("Selecciona «Sugerir una modificación» en la ficha de la entidad para enviar la corrección.");
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
              kind: kind as "source" | "composer" | "work" | "representation",
              entity_id: entityId.trim(),
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
          Contacta con el proyecto o propón una corrección de datos del catálogo. La entidad
          queda asociada automáticamente y las correcciones quedan <em>pendientes de revisión</em>:
          no modifican el catálogo automáticamente.
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

        {kind !== "contact" && !entityId ? (
          <p className="rounded border border-osap-border bg-osap-surface px-3 py-2 text-sm text-osap-muted">
            Para proponer una corrección de {KIND_LABEL[kind].toLowerCase()}, abre su ficha en el
            catálogo y pulsa «Sugerir una modificación»: la entidad se identifica sola.
          </p>
        ) : null}

        {kind === "contact" ? (
          <label className="block text-sm">
            Tu correo (opcional)
            <input
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="mt-1 w-full rounded border border-osap-border px-3 py-2 text-sm"
            />
          </label>
        ) : null}

        {kind === "contact" || entityId ? (
          <>
            <label className="block text-sm">
              Mensaje
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                placeholder="Describe qué hay que corregir (por ejemplo: el título actual y cuál debería ser)."
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
          </>
        ) : null}
      </section>
    </div>
  );
}
