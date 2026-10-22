import { PassThrough } from "node:stream";
import { renderToPipeableStream } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { applySsrState } from "./ssr/applyState";
import type { SsrState } from "./ssr/types";

// Renderizado del árbol React completo para una URL pública. Se usa
// `renderToPipeableStream` + `onAllReady` porque las páginas van por chunks (`React.lazy`):
// `renderToString` se quedaría con el fallback y devolvería HTML vacío.
export function render(url: string, state: SsrState): Promise<string> {
  applySsrState(state);
  return new Promise((resolve, reject) => {
    const stream = new PassThrough();
    let html = "";
    stream.on("data", (chunk: Buffer | string) => {
      html += chunk.toString();
    });
    stream.on("end", () => resolve(html));
    stream.on("error", reject);
    const { pipe } = renderToPipeableStream(
      <MemoryRouter initialEntries={[url]}>
        <App />
      </MemoryRouter>,
      {
        onAllReady() {
          pipe(stream);
        },
        onError(error) {
          reject(error);
        },
      },
    );
  });
}
