// Carga diferida de OpenSheetMusicDisplay y JSZip desde CDN (sin dependencia npm).
//
// OSMD renderiza MusicXML (.musicxml/.xml) y, descomprimiendo antes con JSZip, también
// archivos .mxl (MusicXML comprimido). AlphaTab no se usa: está orientado a Guitar Pro.

type OsmdCtor = new (container: HTMLElement, options?: Record<string, unknown>) => {
  load: (data: string) => Promise<void>;
  render: () => void;
  zoom?: number;
};

declare global {
  interface Window {
    opensheetmusicdisplay?: { OpenSheetMusicDisplay: OsmdCtor };
    JSZip?: JSZipLike;
  }
}

export interface JSZipObjectLike {
  name: string;
  async: (type: "string") => Promise<string>;
}

export interface JSZipLike {
  loadAsync: (data: ArrayBuffer) => Promise<{ files: Record<string, JSZipObjectLike> }>;
}

const OSMD_URL = "https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.8.9/build/opensheetmusicdisplay.min.js";
const JSZIP_URL = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.dataset.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`No se pudo cargar ${src}`));
    document.head.appendChild(script);
  });
}

export async function loadOsmd(): Promise<OsmdCtor> {
  if (!window.opensheetmusicdisplay) {
    await loadScript(OSMD_URL);
  }
  const ctor = window.opensheetmusicdisplay?.OpenSheetMusicDisplay;
  if (!ctor) throw new Error("OpenSheetMusicDisplay no disponible");
  return ctor;
}

export async function loadJSZip(): Promise<JSZipLike> {
  if (!window.JSZip) {
    await loadScript(JSZIP_URL);
  }
  if (!window.JSZip) throw new Error("JSZip no disponible");
  return window.JSZip;
}

/** True si los bytes empiezan por firma ZIP (PK\x03\x04): probable .mxl. */
export function looksLikeZip(bytes: Uint8Array): boolean {
  return bytes.length > 4 && bytes[0] === 0x50 && bytes[1] === 0x4b;
}

/** Extrae el MusicXML de un .mxl: usa META-INF/container.xml o el primer xml. */
export async function musicXmlFromMxl(zip: JSZipLike, data: ArrayBuffer): Promise<string> {
  const archive = await zip.loadAsync(data);
  const files = archive.files;
  const container = files["META-INF/container.xml"];
  if (container) {
    const xml = await container.async("string");
    const match = /full-path="([^"]+)"/i.exec(xml);
    const root = match?.[1];
    if (root && files[root]) {
      return files[root].async("string");
    }
  }
  const first = Object.values(files).find(
    (f) => /\.(musicxml|xml)$/i.test(f.name) && !f.name.startsWith("META-INF")
  );
  if (!first) throw new Error("El .mxl no contiene MusicXML");
  return first.async("string");
}
