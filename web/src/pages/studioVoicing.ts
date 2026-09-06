export const VOICING_STORAGE_KEY = "osap.studio.voicing";

/** Traduce la selección del desplegable Formación vocal al contrato real:
 *  "ALL" (o vacío) = sin filtro -> voices ausente; una formación -> [formación]. */
export function voicingToSearch(voice: string | undefined): string[] | undefined {
  const v = (voice ?? "").trim();
  if (!v || v === "ALL") return undefined;
  return [v];
}

export function loadVoicingSelection(): string {
  try {
    return localStorage.getItem(VOICING_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveVoicingSelection(value: string): void {
  try {
    localStorage.setItem(VOICING_STORAGE_KEY, value);
  } catch {
    /* almacenamiento no disponible */
  }
}
