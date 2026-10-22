import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const pkg = JSON.parse(
  readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "package.json"), "utf8"),
) as { version: string };

// Build del bundle de servidor. Separado del cliente para no tocar `dist/` (los assets
// estáticos que sirve Apache/nginx) al reconstruir el SSR.
export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  plugins: [react(), tailwindcss()],
  // Empaquetar las dependencias del SSR: el servidor no tiene npm ni node_modules.
  ssr: { noExternal: true },
  build: {
    ssr: true,
    outDir: "dist-ssr",
    // No vaciar aquí: con esta configuración Vite vacía `dist/` (el build del cliente).
    // El script `build:ssr` limpia `dist-ssr` antes de compilar.
    emptyOutDir: false,
    rollupOptions: {
      // Solo el entry de servidor: sin esto Vite añade `index.html` (main.tsx) como
      // segundo entry y el bundle acaba con dos copias de los stores (SSR roto).
      input: { "entry-server": "src/entry-server.tsx" },
    },
  },
});
