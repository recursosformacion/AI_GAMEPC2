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
  quantizationInfo: { stepsPerQuarter: number };
}

function pitchOf(note: OsmdNoteLike): number | null {
  const pitch = note.Pitch;
  if (!pitch) return null;
  if (typeof pitch.getHalfTone === "function") return pitch.getHalfTone();
  if (typeof pitch.halfTone === "number") return pitch.halfTone;
  return null;
}

function buildFromSheet(osmd: OsmdLike, bpm: number): NoteSequenceLike | null {
  const measures = osmd.Sheet?.SourceMeasures;
  if (!measures || measures.length === 0) return null;

  const noteSeconds = (wholeFraction: number): number => wholeFraction * 4 * (60 / Math.max(bpm, 1));
  const notes: NoteSequenceLike["notes"] = [];
  let totalTime = 0;

  for (const measure of measures) {
    if (!measure) continue;
    const measureTime = measure.Timestamp?.RealValue ?? totalTime;
    const containers = measure.VerticalSourceStaffEntryContainers ?? [];
    for (const container of containers) {
      if (!container) continue;
      const time = measureTime + (container.Timestamp?.RealValue ?? 0);
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
    totalTime = Math.max(totalTime, measureTime + noteSeconds(measure.Duration?.RealValue ?? 0));
  }

  if (notes.length === 0) return null;
  notes.sort((a, b) => a.startTime - b.startTime);
  const MAX_NOTES = 20000;
  return {
    notes: notes.slice(0, MAX_NOTES),
    totalTime: Math.max(totalTime, 1),
    tempos: [{ time: 0, qpm: bpm }],
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
      const time = iterator.CurrentEnrolledTimestamp?.RealValue ?? steps.length * 0.5;
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
