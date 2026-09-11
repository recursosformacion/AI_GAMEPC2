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
  Sheet?: { SourceMeasures?: Array<{ Timestamp?: { RealValue?: number }; Duration?: { RealValue?: number } }> };
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

export function buildNoteSequence(osmd: OsmdLike, bpm: number): NoteSequenceLike | null {
  const cursor = osmd.cursor;
  const iterator = cursor?.Iterator;
  if (!cursor || !iterator || typeof cursor.NotesUnderCursor !== "function") return null;

  const steps: Array<{ time: number; pitches: number[] }> = [];
  try {
    cursor.reset?.();
    while (!iterator.EndReached) {
      const time = iterator.CurrentEnrolledTimestamp?.RealValue ?? steps.length * 0.5;
      const pitches = (cursor.NotesUnderCursor?.() ?? [])
        .map(pitchOf)
        .filter((p): p is number => typeof p === "number");
      if (pitches.length > 0) steps.push({ time, pitches });
      cursor.next?.();
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
  return {
    notes,
    totalTime,
    tempos: [{ time: 0, qpm: bpm }],
    quantizationInfo: { stepsPerQuarter: 4 },
  };
}
