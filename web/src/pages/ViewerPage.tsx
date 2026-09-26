// Página "Viewer": PDF inline, MusicXML con OSMD + reproducción (osmd-audio-player)
// y MIDI con <midi-player>. Se abre en pestaña nueva desde la ficha de obra.

import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import {
  isMidiContentType,
  loadJSZip,
  loadOsmd,
  looksLikeZip,
  musicXmlFromMxl,
} from "../viewer/osmdLoader";
import { buildNoteSequence, type NoteSequenceLike } from "../viewer/osmdSequence";
import { SynthPlayer } from "../viewer/audioSynth";
import { parseMidi } from "../viewer/midi";
import { limitMeasures } from "../viewer/musicxmlLimit";

type State = "loading" | "rendering" | "ready" | "midi" | "pdf" | "error";

// Compases por página (partituras largas). Con `?measures=all` se carga entera.
const PAGE_MEASURES = 40;

export function ViewerPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const rep = params.get("rep");
  const format = params.get("format");
  const title = params.get("title") ?? "";
  const showAll = params.get("measures") === "all";
  const [page, setPage] = useState(0);
  const [pagination, setPagination] = useState<{ start: number; kept: number; total: number } | null>(
    null
  );
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<SynthPlayer | null>(null);
  const sequenceRef = useRef<NoteSequenceLike | null>(null);
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string>("");
  const [playing, setPlaying] = useState(false);
  const [audioReady, setAudioReady] = useState(false);
  const [audioError, setAudioError] = useState<string>("");
  const [preparing, setPreparing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [seqInfo, setSeqInfo] = useState<string>("");
  const [tempo, setTempo] = useState(100);
  const [volume, setVolume] = useState(80);

  useEffect(() => {
    let alive = true;
    if (!rep) {
      setState("error");
      setMessage(t("viewer.missing"));
      return;
    }
    const run = async () => {
      try {
        setProgress(10);
        const response = await apiClient.fetchRepresentationFile(rep);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setProgress(25);
        const contentType = response.headers.get("content-type") ?? "";
        if (contentType.startsWith("application/pdf")) {
          if (alive) setState("pdf");
          return;
        }
        if (isMidiContentType(contentType, format)) {
          const buffer = await response.arrayBuffer();
          const midi = parseMidi(buffer);
          if (!midi) throw new Error("MIDI no reconocido");
          sequenceRef.current = midi;
          setSeqInfo(`${midi.notes.length} · ${Math.round(midi.totalTime)}s`);
          const midiTempo = midi.tempos[0]?.qpm ?? tempo;
          setTempo(Math.round(midiTempo));
          const midiPlayer = new SynthPlayer(midi, midiTempo);
          midiPlayer.setVolume(volume / 100);
          midiPlayer.onEnd = () => setPlaying(false);
          playerRef.current = midiPlayer;
          setAudioReady(true);
          if (alive) setState("midi");
          return;
        }
        const buffer = await response.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let xml: string;
        if (looksLikeZip(bytes)) {
          xml = await musicXmlFromMxl(await loadJSZip(), buffer);
        } else {
          xml = new TextDecoder("utf-8").decode(bytes);
        }
        if (!alive) return;

        // --- Vista: OSMD paginada (evita renders de decenas de segundos) ---
        let toLoad = xml;
        if (!showAll) {
          const limited = limitMeasures(xml, page * PAGE_MEASURES, PAGE_MEASURES);
          toLoad = limited.xml;
          setPagination({ start: limited.start, kept: limited.kept, total: limited.total });
        } else {
          setPagination(null);
        }
        setState("rendering");
        setProgress(45);
        const OSMD = await loadOsmd();
        if (!containerRef.current || !alive) return;
        setProgress(60);
        const osmd = new OSMD(containerRef.current, {
          autoResize: true,
          backend: "svg",
          // Maquetado compacto: menos sistemas -> menos altura y render más rápido
          // (las partituras largas con el preset por defecto generan cientos de sistemas).
          drawingParameters: "compacttight",
        });
        await osmd.load(toLoad);
        osmd.render();
        setProgress(95);
        if (alive) setState("ready");

        // --- Audio: del modelo OSMD ya cargado (notas de la página mostrada) ---
        try {
          const sequence = buildNoteSequence(
            osmd as unknown as Parameters<typeof buildNoteSequence>[0],
            tempo
          );
          if (!sequence) throw new Error("No se pudieron extraer notas de la partitura");
          sequenceRef.current = sequence;
          setSeqInfo(`${sequence.notes.length} · ${Math.round(sequence.totalTime)}s`);
          const scoreTempo = sequence.tempos[0]?.qpm ?? tempo;
          setTempo(scoreTempo);
          const player = new SynthPlayer(sequence, scoreTempo);
          player.setVolume(volume / 100);
          player.onEnd = () => setPlaying(false);
          playerRef.current = player;
          setAudioReady(true);
          setAudioError("");
        } catch (error) {
          setAudioReady(false);
          setAudioError(error instanceof Error ? error.message : String(error));
        }
      } catch (error) {
        if (!alive) return;
        setState("error");
        setMessage(error instanceof Error ? error.message : String(error));
      }
    };
    void run();
    return () => {
      alive = false;
      playerRef.current?.stop();
      playerRef.current = null;
    };
  }, [rep, format, t, showAll, page]);

  const togglePlay = () => {
    const player = playerRef.current;
    if (!player || preparing) return;
    if (playing) {
      player.pause();
      setPlaying(false);
      return;
    }
    setPreparing(true);
    setAudioError("");
    void player
      .play()
      .then(() => setPlaying(true))
      .catch((error) => setAudioError(error instanceof Error ? error.message : String(error)))
      .finally(() => setPreparing(false));
  };

  const changeTempo = (value: number) => {
    setTempo(value);
    playerRef.current?.setTempo(value);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{title || t("viewer.title")}</h1>
        <div className="flex items-center gap-3">
          {(state === "ready" || state === "midi") && audioReady ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={togglePlay}
                disabled={preparing}
                className="rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60"
              >
                {preparing ? t("viewer.preparing") : playing ? t("viewer.pause") : t("viewer.play")}
              </button>
              <button
                type="button"
                onClick={() => {
                  playerRef.current?.stop();
                  setPlaying(false);
                }}
                className="rounded border border-osap-border px-3 py-1 text-sm"
              >
                {t("viewer.stop")}
              </button>
              <label className="flex items-center gap-1 text-xs text-osap-muted">
                {t("viewer.volume")}
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={volume}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    setVolume(value);
                    playerRef.current?.setVolume(value / 100);
                  }}
                  className="w-20"
                />
              </label>
              <label className="flex items-center gap-1 text-xs text-osap-muted">
                {t("viewer.tempo")}
                <input
                  type="number"
                  min={20}
                  max={300}
                  value={tempo}
                  onChange={(event) => changeTempo(Number(event.target.value))}
                  className="w-16 rounded border border-osap-border px-1 py-0.5"
                />
              </label>
            </div>
          ) : null}
          <a
            className="text-sm text-osap-accent hover:underline"
            href={`/api/v1/representations/${encodeURIComponent(rep ?? "")}/download`}
          >
            {t("actions.download")}
          </a>
        </div>
      </div>

      {pagination ? (
        <div className="flex flex-wrap items-center gap-2 rounded border border-osap-border bg-osap-surface p-2 text-xs text-osap-muted">
          <button
            type="button"
            disabled={pagination.start <= 0}
            onClick={() => setPage((p) => Math.max(p - 1, 0))}
            className="rounded border border-osap-border px-2 py-0.5 disabled:opacity-40"
          >
            ◀
          </button>
          <span>
            {t("viewer.measures")} {pagination.start + 1}–
            {Math.min(pagination.start + pagination.kept, pagination.total)} / {pagination.total}
          </span>
          <button
            type="button"
            disabled={pagination.start + pagination.kept >= pagination.total}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border border-osap-border px-2 py-0.5 disabled:opacity-40"
          >
            ▶
          </button>
          <a
            className="text-osap-accent hover:underline"
            href={`/viewer?rep=${encodeURIComponent(rep ?? "")}&title=${encodeURIComponent(
              title
            )}&measures=all`}
          >
            {t("viewer.showAll")}
          </a>
        </div>
      ) : null}

      {state === "pdf" && rep ? (
        <iframe
          title={title || "PDF"}
          src={`/api/v1/representations/${encodeURIComponent(rep)}/download?view=1`}
          className="h-[80vh] w-full rounded border border-osap-border"
        />
      ) : null}

      {state === "midi" ? (
        <p className="text-sm text-osap-muted">{t("work.download")} · MIDI</p>
      ) : null}

      {state === "ready" && !audioReady ? (
        <p className="text-xs text-osap-muted">
          {t("viewer.audioUnavailable")}
          {audioError ? <span className="ml-1 text-red-600">({audioError})</span> : null}
        </p>
      ) : null}

      {(state === "ready" || state === "midi") && audioReady && seqInfo ? (
        <p className="text-xs text-osap-muted">{seqInfo}</p>
      ) : null}

      {audioReady && audioError ? <p className="text-xs text-red-600">{audioError}</p> : null}

      {state === "loading" || state === "rendering" ? (
        <div className="space-y-1">
          <div className="h-1.5 w-full overflow-hidden rounded bg-osap-surface">
            <div
              className="h-full bg-osap-accent transition-all duration-300"
              style={{ width: `${Math.max(progress, 5)}%` }}
            />
          </div>
          <p className="text-xs text-osap-muted">
            {t("viewer.loading")} {progress}%
          </p>
        </div>
      ) : null}

      {state === "error" ? (
        <div className="rounded border border-osap-border bg-osap-surface p-4 text-sm">
          <p className="text-red-600">{t("viewer.error")}</p>
          {message ? <p className="mt-1 text-osap-muted">{message}</p> : null}
          <Link to="/" className="mt-2 inline-block text-osap-accent hover:underline">
            ← {t("nav.home")}
          </Link>
        </div>
      ) : null}

      <div ref={containerRef} className="overflow-x-auto" />
    </div>
  );
}
