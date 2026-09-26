// Reproductor de partitura con WebAudio nativo (sin dependencias ni CDN).
//
// Estrategia "mobile-first" y apta para piezas MUY largas: en vez de renderizar toda la
// pieza de una vez (que tarda decenas de segundos y agota memoria), se programan los
// osciladores por VENTANAS: se empieza a sonar de inmediato y se van agendando ~15 s de
// partitura por delante, reciclando nodos ya terminados. Así el arranque es inmediato y
// nunca hay miles de osciladores vivos.
//
// API estable: `play()`, `pause()`, `stop()`, `setVolume()`, `setTempo()`, `onEnd`.

import type { NoteSequenceLike } from "./osmdSequence";

export function midiToFrequency(pitch: number): number {
  return 440 * Math.pow(2, (pitch - 69) / 12);
}

type AudioContextCtor = typeof AudioContext;

function resolveAudioContextCtor(): AudioContextCtor {
  const w = window as unknown as {
    AudioContext?: AudioContextCtor;
    webkitAudioContext?: AudioContextCtor;
  };
  const ctor = w.AudioContext ?? w.webkitAudioContext;
  if (!ctor) throw new Error("Web Audio no disponible en este navegador");
  return ctor;
}

const WINDOW_SCORE_SECONDS = 15; // partitura agendada por delante
const TICK_MS = 500; // frecuencia de comprobación del agendado

interface LiveNode {
  osc: OscillatorNode;
  endReal: number;
}

export class SynthPlayer {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private live: LiveNode[] = [];
  private timer: number | null = null;
  private startedAt = 0; // ctx time correspondiente al inicio de la partitura (score 0)
  private scheduledUpTo = 0; // segundos de partitura ya agendados
  private offset = 0; // posición en segundos de partitura
  private playing = false;
  private bpm: number;
  private readonly baseQpm: number;
  private volume = 0.8;
  private readonly notes: NoteSequenceLike["notes"];
  private readonly totalScore: number;

  onEnd: (() => void) | null = null;

  constructor(sequence: NoteSequenceLike, bpm: number) {
    // Orden por inicio para poder cortar el bucle por ventana.
    this.notes = [...sequence.notes].sort((a, b) => a.startTime - b.startTime);
    this.bpm = Math.max(bpm, 20);
    this.baseQpm = Math.max(sequence.tempos?.[0]?.qpm ?? bpm, 20);
    this.totalScore = this.notes.reduce((max, n) => Math.max(max, n.endTime), 0);
  }

  /** Tiempo real por segundo de partitura (1 = tempo original). */
  private get speed(): number {
    return this.baseQpm / this.bpm;
  }

  private context(): AudioContext {
    if (!this.ctx) {
      const Ctor = resolveAudioContextCtor();
      this.ctx = new Ctor();
    }
    return this.ctx;
  }

  private masterGain(): GainNode {
    const ctx = this.context();
    if (!this.master) {
      this.master = ctx.createGain();
      this.master.gain.value = this.volume;
      this.master.connect(ctx.destination);
    }
    return this.master;
  }

  setVolume(value: number): void {
    this.volume = Math.min(Math.max(value, 0), 1);
    if (this.master) this.master.gain.value = this.volume;
  }

  /** Agenda una ventana de notas a partir de `fromScore` (segundos de partitura). */
  private scheduleWindow(fromScore: number): void {
    const ctx = this.context();
    const master = this.masterGain();
    const to = Math.min(fromScore + WINDOW_SCORE_SECONDS, this.totalScore);
    for (const note of this.notes) {
      if (note.endTime <= fromScore) continue;
      if (note.startTime >= to) break;
      const startScore = Math.max(note.startTime, fromScore);
      const when = this.startedAt + startScore * this.speed;
      const dur = Math.max((note.endTime - startScore) * this.speed, 0.05);
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = midiToFrequency(note.pitch);
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.linearRampToValueAtTime(0.18, when + 0.01);
      gain.gain.setValueAtTime(0.18, Math.max(when + 0.02, when + dur - 0.03));
      gain.gain.linearRampToValueAtTime(0.0001, when + dur);
      osc.connect(gain).connect(master);
      osc.start(when);
      osc.stop(when + dur + 0.02);
      this.live.push({ osc, endReal: when + dur + 0.02 });
    }
    this.scheduledUpTo = to;
  }

  private prune(): void {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    this.live = this.live.filter((n) => {
      if (n.endReal < now - 1) {
        try {
          n.osc.disconnect();
        } catch {
          /* ya desconectado */
        }
        return false;
      }
      return true;
    });
  }

  private tick = (): void => {
    if (!this.playing || !this.ctx) return;
    this.prune();
    const nowReal = this.ctx.currentTime;
    const nowScore = (nowReal - this.startedAt) / this.speed;
    if (this.scheduledUpTo < this.totalScore) {
      if (this.scheduledUpTo - nowScore < WINDOW_SCORE_SECONDS / 2) {
        this.scheduleWindow(this.scheduledUpTo);
      }
    } else if (nowReal >= this.startedAt + this.totalScore * this.speed) {
      this.playing = false;
      this.offset = 0;
      this.stopTimer();
      this.onEnd?.();
    }
    this.ensureTimer();
  };

  private ensureTimer(): void {
    if (this.timer === null && this.playing) {
      this.timer = window.setInterval(this.tick, TICK_MS);
    }
  }

  private stopTimer(): void {
    if (this.timer !== null) {
      window.clearInterval(this.timer);
      this.timer = null;
    }
  }

  private stopNodes(): void {
    for (const n of this.live) {
      try {
        n.osc.stop();
      } catch {
        /* ya detenido */
      }
      try {
        n.osc.disconnect();
      } catch {
        /* ya desconectado */
      }
    }
    this.live = [];
  }

  async play(): Promise<void> {
    const ctx = this.context(); // crear/reanudar dentro del gesto del usuario
    if (ctx.state === "suspended") await ctx.resume();
    this.stopNodes();
    this.startedAt = ctx.currentTime - this.offset * this.speed;
    this.scheduledUpTo = this.offset;
    this.playing = true;
    this.scheduleWindow(this.offset); // primer tramo: suena de inmediato
    this.ensureTimer();
  }

  pause(): void {
    if (!this.ctx || !this.playing) return;
    this.offset = Math.max((this.ctx.currentTime - this.startedAt) / this.speed, 0);
    this.playing = false;
    this.stopTimer();
    this.stopNodes();
  }

  stop(): void {
    this.playing = false;
    this.offset = 0;
    this.stopTimer();
    this.stopNodes();
  }

  setTempo(bpm: number): void {
    const next = Math.max(bpm, 20);
    if (this.playing) {
      this.pause();
      this.bpm = next;
      void this.play();
      return;
    }
    this.bpm = next;
  }
}
