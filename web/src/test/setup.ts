import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/dom";

// Las páginas usan React.lazy (code-splitting). En la suite completa, la carga de chunks
// compite con el resto de workers y el timeout por defecto (1 s) provoca fallos falsos.
configure({ asyncUtilTimeout: 5000 });

// jsdom no implementa ResizeObserver y los componentes que miden su área (AdSlot) lo usan.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}
