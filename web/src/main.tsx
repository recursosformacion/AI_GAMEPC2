import { Component, StrictMode, type ErrorInfo, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./design-system/tokens.css";

// Tras un despliegue, una pestaña abierta con el bundle anterior pide chunks que ya no
// existen (404) y la app se quedaba en blanco. Vite emite `vite:preloadError`: recargamos
// una vez (con guarda para no entrar en bucle) y la pestaña pasa al bundle nuevo.
window.addEventListener("vite:preloadError", () => {
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
});

// Red de seguridad: nunca dejar la pantalla en blanco. Un error de render muestra un aviso
// y un botón de recarga (con el texto sin depender del i18n, que podría ser el que falló).
class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("OSAP render error", error, info);
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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
