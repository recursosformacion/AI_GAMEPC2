import { useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useAuth } from "../state/auth";

type RepresentationRef = {
  id?: string | null;
  provider?: string | null;
  format?: string | null;
};

interface SaveToWorkspaceButtonProps {
  workId: string;
  workTitle?: string | null;
  composer?: string | null;
  representation: RepresentationRef;
}

type SaveState = "idle" | "saving" | "saved" | "error";

export function SaveToWorkspaceButton({
  workId,
  workTitle,
  composer,
  representation,
}: SaveToWorkspaceButtonProps) {
  const isAuthenticated = useAuth((s) => s.isAuthenticated());
  const [state, setState] = useState<SaveState>("idle");

  if (!isAuthenticated) return null;

  const save = async () => {
    setState("saving");
    try {
      await apiClient.saveWorkspaceReference({
        provider: representation.provider ?? "osap",
        work_id: workId,
        representation_id: representation.id ?? null,
        title: workTitle || "Obra de OSAP",
        subtitle: composer ?? null,
        metadata: { format: representation.format ?? null },
      });
      setState("saved");
    } catch {
      setState("error");
    }
  };

  const label =
    state === "saving"
      ? "Guardando…"
      : state === "saved"
        ? "Guardado"
        : state === "error"
          ? "Reintentar"
          : "Guardar";

  return (
    <button
      type="button"
      onClick={() => void save()}
      disabled={state === "saving" || state === "saved"}
      title="Guardar esta referencia en mi espacio de trabajo"
      className="inline-flex h-9 items-center rounded border border-osap-border-strong px-2 text-xs font-medium text-osap-accent hover:bg-osap-accent-soft disabled:opacity-60"
    >
      {label}
    </button>
  );
}
