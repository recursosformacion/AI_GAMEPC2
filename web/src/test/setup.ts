import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/dom";

// Las páginas usan React.lazy (code-splitting). En la suite completa, la carga de chunks
// compite con el resto de workers y el timeout por defecto (1 s) provoca fallos falsos.
configure({ asyncUtilTimeout: 5000 });
