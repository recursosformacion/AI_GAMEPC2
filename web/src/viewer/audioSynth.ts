// Reproductor de partitura con WebAudio nativo (sin dependencias ni CDN).
// Reproduce el NoteSequence extraído de OSMD con un oscilador sencillo + envelope.

import type { NoteSequenceLike } from "./osmdSequence";

export function midiToFrequency(pitch: number): number {
  return 440 * Math.pow(2, (pitch - 69) / 12);
}

export class SynthPlayer {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private nodes: OscillatorNode[] = [];
  private startedAt = 0; // ctx time corresponding to score time 0 (según bpm actual)
  private offset = 0; // posición en "segundos de partitura"
  private playing = false;
  private bpm: number;
  private readonly baseQpm: number;
  private volume = 0.8;
  private readonly notes: NoteSequenceLike["notes"];

  onEnd: (() => void) | null = null;

  constructor(sequence: NoteSequenceLike, bpm: number) {
    this.notes = sequence.notes;
    this.bpm = Math.max(bpm, 20);
    // Tempo de la partitura: los tiempos del NoteSequence están en segundos a ese tempo.
    this.baseQpm = Math.max(sequence.tempos?.[0]?.qpm ?? bpm, 20);
  }

  private context(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
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

  private get speed(): number {
    // Tiempo real por segundo de partitura: 1 si se reproduce al tempo original.
    return this.baseQpm / this.bpm;
  }

  private schedule(fromScore: number): void {
    const ctx = this.context();
    const master = this.masterGain();
    const lastEnd = this.notes.reduce((max, n) => Math.max(max, n.endTime), 0);
    for (const note of this.notes) {
      if (note.endTime <= fromScore) continue;
      const startScore = Math.max(note.startTime, fromScore);
      const when = this.startedAt + startScore * this.speed;
      const duration = Math.max((note.endTime - startScore) * this.speed, 0.05);
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = midiToFrequency(note.pitch);
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.linearRampToValueAtTime(0.18, when + 0.01);
      gain.gain.setValueAtTime(0.18, Math.max(when + 0.02, when + duration - 0.03));
      gain.gain.linearRampToValueAtTime(0.0001, when + duration);
      osc.connect(gain).connect(master);
      osc.start(when);
      osc.stop(when + duration + 0.02);
      this.nodes.push(osc);
    }
    const endAt = this.startedAt + lastEnd * this.speed;
    const timer = window.setTimeout(
      () => {
        this.playing = false;
        this.offset = 0;
        this.nodes = [];
        this.onEnd?.();
      },
      Math.max((endAt - ctx.currentTime) * 1000, 0)
    );
    this.nodes.push({ stop: () => window.clearTimeout(timer) } as unknown as OscillatorNode);
  }

  private stopNodes(): void {
    for (const node of this.nodes) {
      try {
        node.stop();
      } catch {
        /* nodo ya detenido */
      }
    }
    this.nodes = [];
  }

  async play(): Promise<void> {
    const ctx = this.context();
    if (ctx.state === "suspended") await ctx.resume();
    this.startedAt = ctx.currentTime - this.offset * this.speed;
    this.playing = true;
    this.schedule(this.offset);
  }

  pause(): void {
    if (!this.ctx || !this.playing) return;
    this.offset = Math.max((this.ctx.currentTime - this.startedAt) / this.speed, 0);
    this.stopNodes();
    this.playing = false;
  }

  stop(): void {
    this.stopNodes();
    this.offset = 0;
    this.playing = false;
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
