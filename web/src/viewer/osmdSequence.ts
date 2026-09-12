// Convierte la partitura cargada en OSMD a un NoteSequence de Magenta (para reproducir
// con Tone/Magenta sin depender de osmd-audio-player).

interface OsmdNoteLike {
  Pitch?: { getHalfTone?: () => number; halfTone?: number } | null;
}

interface OsmdCursorIteratorLike {
  EndReached: boolean;
  CurrentEnrolledTimestamp?: { RealValue?: number } | null;
}

interface OsmdCursorLike {
  Iterator?: OsmdCursorIteratorLike;
  reset?: () => void;
  next?: () => void;
  NotesUnderCursor?: () => OsmdNoteLike[];
}

interface OsmdLike {
  cursor?: OsmdCursorLike;
  Sheet?: {
    DefaultStartTempoInBpm?: number;
    SourceMeasures?: Array<{
      Timestamp?: { RealValue?: number };
      Duration?: { RealValue?: number };
      VerticalSourceStaffEntryContainers?: Array<{
        Timestamp?: { RealValue?: number };
        StaffEntries?: Array<{
          VoiceEntries?: Array<{ Notes?: OsmdNoteLike[] }>;
        }>;
      }>;
    }>;
  };
}

interface OsmdNoteLikeWithLength extends OsmdNoteLike {
  Length?: { RealValue?: number };
}

export interface NoteSequenceLike {
  notes: Array<{ pitch: number; startTime: number; endTime: number; program?: number }>;
  totalTime: number;
  tempos: Array<{ time: number; qpm: number }>;
  quantizationInfo?: { stepsPerQuarter: number };
}

// OSMD 0.8.4 usa `halfTone = fundamental + 12*(octave + 3)`, que sitúa C4 en 48 en
// lugar del MIDI estándar 60: hay que subir una octava para que suene a la altura real.
const OSMD_MIDI_OCTAVE_FIX = 12;

// OSMD expresa timestamps/duraciones en redondas (whole notes = RealValue), no en segundos.
// Sin convertir, la reproducción sonaba a golpes y con silencios.
function wholeToSeconds(whole: number, qpm: number): number {
  return whole * 4 * (60 / Math.max(qpm, 20));
}

function pitchOf(note: OsmdNoteLike): number | null {
  const pitch = note.Pitch;
  if (!pitch) return null;
  const raw =
    typeof pitch.getHalfTone === "function"
      ? pitch.getHalfTone()
      : typeof pitch.halfTone === "number"
        ? pitch.halfTone
        : null;
  if (typeof raw !== "number") return null;
  return Math.min(Math.max(raw + OSMD_MIDI_OCTAVE_FIX, 0), 127);
}

function buildFromSheet(osmd: OsmdLike, bpm: number): NoteSequenceLike | null {
  const measures = osmd.Sheet?.SourceMeasures;
  if (!measures || measures.length === 0) return null;

  // Los timestamps de OSMD ya vienen en segundos según el tempo de la partitura; las
  // duraciones deben usar ese mismo tempo para no producir huecos ("a golpes").
  const scoreBpm = Math.max(osmd.Sheet?.DefaultStartTempoInBpm ?? bpm, 20);
  const noteSeconds = (wholeFraction: number): number => wholeToSeconds(wholeFraction, scoreBpm);
  const notes: NoteSequenceLike["notes"] = [];
  let totalTime = 0;

  for (const measure of measures) {
    if (!measure) continue;
    const measureTime = measure.Timestamp?.RealValue ?? 0;
    const containers = measure.VerticalSourceStaffEntryContainers ?? [];
    for (const container of containers) {
      if (!container) continue;
      // `container.Timestamp` es absoluto en OSMD; si viniera relativo al compás, se ancla.
      const rawContainer = container.Timestamp?.RealValue;
      const absoluteWhole =
        rawContainer === undefined
          ? measureTime
          : rawContainer < measureTime - 1e-6
            ? measureTime + rawContainer
            : rawContainer;
      const time = noteSeconds(absoluteWhole);
      for (const staffEntry of container.StaffEntries ?? []) {
        if (!staffEntry) continue;
        for (const voiceEntry of staffEntry.VoiceEntries ?? []) {
          if (!voiceEntry) continue;
          for (const note of (voiceEntry.Notes ?? []) as OsmdNoteLikeWithLength[]) {
            if (!note) continue;
            const pitch = pitchOf(note);
            if (typeof pitch !== "number") continue;
            const duration = noteSeconds(note.Length?.RealValue ?? 0.25);
            notes.push({ pitch, startTime: time, endTime: time + duration, program: 0 });
            totalTime = Math.max(totalTime, time + duration);
          }
        }
      }
    }
    totalTime = Math.max(totalTime, noteSeconds(measureTime + (measure.Duration?.RealValue ?? 0)));
  }

  if (notes.length === 0) return null;
  notes.sort((a, b) => a.startTime - b.startTime);
  const MAX_NOTES = 20000;
  return {
    notes: notes.slice(0, MAX_NOTES),
    totalTime: Math.max(totalTime, 1),
    tempos: [{ time: 0, qpm: scoreBpm }],
    quantizationInfo: { stepsPerQuarter: 4 },
  };
}

export function buildNoteSequence(osmd: OsmdLike, bpm: number): NoteSequenceLike | null {
  // 1) Modelo de la partitura (completo y determinista).
  let fromSheet: NoteSequenceLike | null = null;
  try {
    fromSheet = buildFromSheet(osmd, bpm);
  } catch {
    fromSheet = null;
  }
  if (fromSheet) return fromSheet;

  // 2) Fallback: recorrido por el cursor (con límites de seguridad).
  const cursor = osmd.cursor;
  const iterator = cursor?.Iterator;
  if (!cursor || !iterator || typeof cursor.NotesUnderCursor !== "function") return null;
  if (typeof cursor.next !== "function" || typeof cursor.reset !== "function") return null;

  const MAX_STEPS = 8000;
  const steps: Array<{ time: number; pitches: number[] }> = [];
  try {
    cursor.reset();
    let guard = 0;
    let prevTime = Number.NaN;
    let sameTime = 0;
    while (!iterator.EndReached) {
      guard += 1;
      if (guard > MAX_STEPS) break; // seguridad: evita cuelgues si el cursor no avanza
      const timeWhole = iterator.CurrentEnrolledTimestamp?.RealValue ?? steps.length * 0.5;
      const time = wholeToSeconds(timeWhole, bpm);
      // Si la marca no avanza varias iteraciones seguidas, cortamos (cursor bloqueado).
      if (time === prevTime) {
        sameTime += 1;
        if (sameTime > 8) break;
      } else {
        sameTime = 0;
        prevTime = time;
      }
      const pitches = (cursor.NotesUnderCursor?.() ?? [])
        .map(pitchOf)
        .filter((p): p is number => typeof p === "number");
      if (pitches.length > 0) steps.push({ time, pitches });
      cursor.next();
    }
  } catch {
    return null;
  }
  if (steps.length === 0) return null;

  const notes: NoteSequenceLike["notes"] = [];
  for (let i = 0; i < steps.length; i += 1) {
    const step = steps[i];
    if (!step) continue;
    const next = steps[i + 1];
    const start = step.time;
    const end = next ? next.time : start + 60 / Math.max(bpm, 1);
    for (const pitch of step.pitches) {
      notes.push({ pitch, startTime: start, endTime: Math.max(end, start + 0.05), program: 0 });
    }
  }
  const lastStep = steps[steps.length - 1];
  const totalTime = Math.max((lastStep?.time ?? 0) + 60 / Math.max(bpm, 1), 1);
  const MAX_NOTES = 20000;
  return {
    notes: notes.slice(0, MAX_NOTES),
    totalTime,
    tempos: [{ time: 0, qpm: bpm }],
    quantizationInfo: { stepsPerQuarter: 4 },
  };
}
