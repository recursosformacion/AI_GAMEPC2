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

const OSMD_URL = "https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@0.8.4/build/opensheetmusicdisplay.min.js";
const JSZIP_URL = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
const AUDIO_PLAYER_URL = "https://cdn.jsdelivr.net/npm/osmd-audio-player@0.7.0/umd/OsmdAudioPlayer.min.js";
// Bundle documentado de html-midi-player: Tone + Magenta core + focus-visible + player.
const MIDI_PLAYER_URL =
  "https://cdn.jsdelivr.net/combine/npm/tone@14.7.58,npm/@magenta/music@1.23.1/es6/core.js,npm/focus-visible@5,npm/html-midi-player@1.4.0";

export interface AudioPlayerLike {
  load: () => Promise<void>;
  play: () => void;
  pause: () => void;
  stop: () => void;
  setBpm?: (bpm: number) => void;
  on?: (event: string, listener: (state: string) => void) => void;
  state?: string;
}

export type AudioPlayerCtor = new (osmd: unknown) => AudioPlayerLike;

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

/** Carga el reproductor de OSMD (UMD) y devuelve su constructor. */
export async function loadAudioPlayer(): Promise<AudioPlayerCtor> {
  const raw = (window as unknown as { OsmdAudioPlayer?: unknown }).OsmdAudioPlayer;
  if (!raw) {
    await loadScript(AUDIO_PLAYER_URL);
  }
  const loaded = (window as unknown as { OsmdAudioPlayer?: unknown }).OsmdAudioPlayer;
  const ctor =
    typeof loaded === "function"
      ? (loaded as AudioPlayerCtor)
      : (loaded as { OsmdAudioPlayer?: AudioPlayerCtor } | undefined)?.OsmdAudioPlayer;
  if (!ctor) throw new Error("Reproductor de audio no disponible");
  return ctor;
}

/** Carga el elemento <midi-player> (para representaciones MIDI). */
export async function loadMidiPlayer(): Promise<void> {
  if (customElements.get("midi-player")) return;
  await loadScript(MIDI_PLAYER_URL);
}

export function isMidiContentType(contentType: string, format?: string | null): boolean {
  const fmt = (format ?? "").toLowerCase();
  return contentType.startsWith("audio/midi") || contentType.includes("midi") || fmt === "midi";
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
