// Página "Viewer": PDF inline, MusicXML con OSMD + reproducción (osmd-audio-player)
// y MIDI con <midi-player>. Se abre en pestaña nueva desde la ficha de obra.

import { createElement, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import {
  isMidiContentType,
  loadJSZip,
  loadMidiPlayer,
  loadOsmd,
  looksLikeZip,
  musicXmlFromMxl,
} from "../viewer/osmdLoader";
import { buildNoteSequence, type NoteSequenceLike } from "../viewer/osmdSequence";
import { SynthPlayer } from "../viewer/audioSynth";

type State = "loading" | "rendering" | "ready" | "midi" | "pdf" | "error";

export function ViewerPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const rep = params.get("rep");
  const format = params.get("format");
  const title = params.get("title") ?? "";
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<SynthPlayer | null>(null);
  const sequenceRef = useRef<NoteSequenceLike | null>(null);
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string>("");
  const [playing, setPlaying] = useState(false);
  const [audioReady, setAudioReady] = useState(false);
  const [audioError, setAudioError] = useState<string>("");
  const [seqInfo, setSeqInfo] = useState<string>("");
  const [tempo, setTempo] = useState(100);

  useEffect(() => {
    let alive = true;
    if (!rep) {
      setState("error");
      setMessage(t("viewer.missing"));
      return;
    }
    const run = async () => {
      try {
        const response = await apiClient.fetchRepresentationFile(rep);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const contentType = response.headers.get("content-type") ?? "";
        if (contentType.startsWith("application/pdf")) {
          if (alive) setState("pdf");
          return;
        }
        if (isMidiContentType(contentType, format)) {
          await loadMidiPlayer();
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
        setState("rendering");
        const OSMD = await loadOsmd();
        if (!containerRef.current || !alive) return;
        const osmd = new OSMD(containerRef.current, { autoResize: true, backend: "svg" });
        await osmd.load(xml);
        osmd.render();
        if (alive) setState("ready");
        try {
          const sequence = buildNoteSequence(
            osmd as unknown as Parameters<typeof buildNoteSequence>[0],
            tempo
          );
          if (!sequence) throw new Error("No se pudieron extraer notas de la partitura");
          sequenceRef.current = sequence;
          setSeqInfo(`${sequence.notes.length} · ${Math.round(sequence.totalTime)}s`);
          const player = new SynthPlayer(sequence, tempo);
          player.onEnd = () => {
            setPlaying(false);
          };
          playerRef.current = player;
          setAudioReady(true);
        } catch (error) {
          setAudioReady(false); // render sin sonido: no es un error bloqueante
          setAudioError(error instanceof Error ? error.message : String(error));
          // eslint-disable-next-line no-console
          console.error("audio:", error);
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
  }, [rep, format, t]);

  const togglePlay = () => {
    const player = playerRef.current;
    if (!player) return;
    if (playing) {
      player.pause();
      setPlaying(false);
      return;
    }
    void player.play().then(() => {
      setPlaying(true);
    });
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
          {state === "ready" && audioReady ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={togglePlay}
                className="rounded bg-osap-accent px-3 py-1 text-sm text-white"
              >
                {playing ? t("viewer.pause") : t("viewer.play")}
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

      {state === "pdf" && rep ? (
        <iframe
          title={title || "PDF"}
          src={`/api/v1/representations/${encodeURIComponent(rep)}/download?view=1`}
          className="h-[80vh] w-full rounded border border-osap-border"
        />
      ) : null}

      {state === "midi" && rep
        ? createElement("midi-player", {
            src: `/api/v1/representations/${encodeURIComponent(rep)}/download?view=1`,
            "sound-font": true,
          })
        : null}

      {state === "ready" && !audioReady ? (
        <p className="text-xs text-osap-muted">
          {t("viewer.audioUnavailable")}
          {audioError ? <span className="ml-1 text-red-600">({audioError})</span> : null}
        </p>
      ) : null}

      {state === "ready" && audioReady && seqInfo ? (
        <p className="text-xs text-osap-muted">{seqInfo}</p>
      ) : null}

      {state === "loading" || state === "rendering" ? (
        <p className="text-sm text-osap-muted">{t("viewer.loading")}</p>
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
