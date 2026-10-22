import { Component, StrictMode, type ErrorInfo, type ReactNode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { applySsrState } from "./ssr/applyState";
import "./design-system/tokens.css";

// Tras un despliegue, una pestaña abierta con el bundle anterior pide chunks que ya no
// existen (404) y la app se quedaba en blanco. Vite emite `vite:preloadError`: recargamos
// una vez (con guarda para no entrar en bucle) y la pestaña pasa al bundle nuevo.
window.addEventListener("vite:preloadError", () => reloadOnce());

// Red de seguridad: nunca dejar la pantalla en blanco. Si el error es de carga de un chunk
// (bundle antiguo tras un despliegue), se recarga sola; si es otro, muestra el detalle y un
// botón de recarga. El texto no depende del i18n, que podría ser justo lo que falló.
function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /dynamically imported module|Importing a module script failed|Loading chunk|Failed to fetch/i.test(
    message,
  );
}

function reloadOnce(): void {
  const KEY = "osap.chunkReloadAt";
  let last = 0;
  try {
    last = Number(sessionStorage.getItem(KEY) ?? "0");
  } catch {
    /* almacenamiento no disponible */
  }
  if (Date.now() - last < 10_000) return;
  try {
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    /* almacenamiento no disponible */
  }
  window.location.reload();
}

class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean; detail: string }
> {
  state = { failed: false, detail: "" };

  static getDerivedStateFromError(error: unknown): { failed: boolean; detail: string } {
    const detail = error instanceof Error ? error.message : String(error ?? "");
    return { failed: true, detail: detail.slice(0, 300) };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("OSAP render error", error, info);
    if (isChunkLoadError(error)) reloadOnce();
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div
        style={{
          maxWidth: 560,
          margin: "4rem auto",
          padding: "0 1rem",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Algo ha fallado</h1>
        <p style={{ marginTop: ".5rem", fontSize: ".9rem", color: "#555" }}>
          Recarga la página para continuar. Si acabas de actualizar, puede ser una versión
          antigua en caché.
        </p>
        {this.state.detail ? (
          <p style={{ marginTop: ".5rem", fontSize: ".75rem", color: "#888", wordBreak: "break-word" }}>
            {this.state.detail}
          </p>
        ) : null}
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{ marginTop: "1rem", padding: ".4rem .9rem", cursor: "pointer" }}
        >
          Recargar
        </button>
      </div>
    );
  }
}

const root = document.getElementById("root")!;
// El SSR deja el estado ya cargado en `window.__OSAP_STATE__`; se aplica antes de hidratar
// para que el primer render del cliente sea idéntico al HTML del servidor.
applySsrState(window.__OSAP_STATE__);
const tree = (
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>
);
if (root.hasChildNodes()) {
  hydrateRoot(root, tree);
} else {
  createRoot(root).render(tree);
}
