import { useCallback, useRef, useState } from "react";
import { htmlToText, textToHtml } from "../utils/richtext";

// Heurística de HTML para el cuerpo (mismo criterio que el saneado del servidor).
const HTML_TAG = /<\s*\/?\s*[a-zA-Z][^>]*>/;

export function looksLikeHtml(text: string): boolean {
  return HTML_TAG.test(text);
}

export type BodyMode = "text" | "code";

// Estado del cuerpo del artículo con conmutador Texto/Código **sin pérdidas**:
// - Se abre en `code` si el cuerpo ya es HTML (evita tratar HTML como texto).
// - Al pasar a Texto se recuerda el HTML; al volver a Código se restaura si el texto no se
//   ha editado. Así alternar no escapa ni destruye la codificación.
// - Nunca escapa un cuerpo que ya parece HTML.
export function useBodyMode(
  initial: string,
  initialMode?: BodyMode,
): {
  body: string;
  setBody: (value: string) => void;
  mode: BodyMode;
  toggle: () => void;
  load: (value: string) => void;
} {
  const [body, setBodyState] = useState(initial);
  const [mode, setMode] = useState<BodyMode>(
    initialMode ?? (looksLikeHtml(initial) ? "code" : "text"),
  );
  const stash = useRef<{ html: string; text: string } | null>(null);

  const setBody = useCallback((value: string) => setBodyState(value), []);

  // Carga inicial (p. ej. un artículo existente): fija cuerpo y modo según el contenido.
  const load = useCallback((value: string) => {
    stash.current = null;
    setBodyState(value);
    setMode(initialMode ?? (looksLikeHtml(value) ? "code" : "text"));
  }, [initialMode]);

  const toggle = useCallback(() => {
    if (mode === "text") {
      setBodyState((current) => {
        const saved = stash.current;
        if (saved !== null && saved.text === current) return saved.html;
        return looksLikeHtml(current) ? current : textToHtml(current);
      });
      setMode("code");
      return;
    }
    setBodyState((current) => {
      const text = htmlToText(current);
      stash.current = { html: current, text };
      return text;
    });
    setMode("text");
  }, [mode]);

  return { body, setBody, mode, toggle, load };
}
