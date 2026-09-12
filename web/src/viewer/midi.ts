// Parser mínimo de Standard MIDI File (SMF) para reproducir con el sintetizador WebAudio.
// Sin dependencias externas: solo necesita obtener las notas (pitch + tiempos) y el tempo.

export interface MidiSequence {
  notes: Array<{ pitch: number; startTime: number; endTime: number; program?: number }>;
  totalTime: number;
  tempos: Array<{ time: number; qpm: number }>;
}

function readVarLen(view: DataView, offset: { value: number }): number {
  let value = 0;
  for (;;) {
    const byte = view.getUint8(offset.value);
    offset.value += 1;
    value = (value << 7) | (byte & 0x7f);
    if ((byte & 0x80) === 0) return value;
  }
}

export function parseMidi(data: ArrayBuffer): MidiSequence | null {
  const view = new DataView(data);
  const len = view.byteLength;
  if (len < 14 || view.getUint32(0) !== 0x4d546864) return null; // "MThd"
  const division = view.getUint16(12);
  if (division & 0x8000) return null; // SMPTE: no soportado
  const ticksPerBeat = division || 480;

  interface RawNote {
    pitch: number;
    start: number;
    end: number;
  }
  const rawNotes: RawNote[] = [];
  const tempos: Array<{ tick: number; qpm: number }> = [{ tick: 0, qpm: 120 }];

  let offset = { value: 14 };
  while (offset.value + 8 <= len) {
    const id = view.getUint32(offset.value);
    const size = view.getUint32(offset.value + 4);
    offset.value += 8;
    const end = Math.min(offset.value + size, len);
    if (id !== 0x4d54726b) {
      offset.value = end; // "MTrk"
      continue;
    }
    let tick = 0;
    let status = 0;
    const active = new Map<number, { pitch: number; start: number }>();
    while (offset.value < end) {
      tick += readVarLen(view, offset);
      let byte = view.getUint8(offset.value);
      if (byte & 0x80) {
        status = byte;
        offset.value += 1;
      }
      const type = status & 0xf0;
      const channel = status & 0x0f;
      if (status === 0xff) {
        const metaType = view.getUint8(offset.value);
        offset.value += 1;
        const metaLen = readVarLen(view, offset);
        const metaEnd = offset.value + metaLen;
        if (metaType === 0x51 && metaLen >= 3) {
          const microsPerQuarter = view.getUint8(offset.value) * 65536 + view.getUint16(offset.value + 1);
          tempos.push({ tick, qpm: 60_000_000 / microsPerQuarter });
        }
        offset.value = Math.min(metaEnd, end);
        byte = 0;
        continue;
      }
      if (type === 0x90 || type === 0x80) {
        const pitch = view.getUint8(offset.value);
        const velocity = view.getUint8(offset.value + 1);
        offset.value += 2;
        const key = channel * 128 + pitch;
        if (type === 0x90 && velocity > 0) {
          active.set(key, { pitch, start: tick });
        } else {
          const note = active.get(key);
          if (note) {
            rawNotes.push({ pitch: note.pitch, start: note.start, end: tick });
            active.delete(key);
          }
        }
      } else if (type === 0xa0 || type === 0xb0 || type === 0xe0) {
        offset.value += 2;
      } else if (type === 0xc0) {
        offset.value += 1;
      } else if (type === 0xd0) {
        offset.value += 1;
      } else {
        offset.value += 1; // evento desconocido: evita bucle infinito
      }
    }
    offset.value = end;
  }

  if (rawNotes.length === 0) return null;
  tempos.sort((a, b) => a.tick - b.tick);
  const secondsPerTick = (tick: number): number => {
    let seconds = 0;
    let currentQpm = tempos[0]?.qpm ?? 120;
    let previousTick = 0;
    for (const tempo of tempos) {
      if (tempo.tick >= tick) break;
      seconds += ((tempo.tick - previousTick) / ticksPerBeat) * (60 / currentQpm);
      previousTick = tempo.tick;
      currentQpm = tempo.qpm;
    }
    seconds += ((tick - previousTick) / ticksPerBeat) * (60 / currentQpm);
    return seconds;
  };

  const notes = rawNotes.map((n) => ({
    pitch: n.pitch,
    startTime: secondsPerTick(n.start),
    endTime: Math.max(secondsPerTick(n.end), secondsPerTick(n.start) + 0.05),
    program: 0,
  }));
  const totalTime = notes.reduce((max, n) => Math.max(max, n.endTime), 0);
  return {
    notes,
    totalTime: Math.max(totalTime, 0.5),
    tempos: [{ time: 0, qpm: tempos[0]?.qpm ?? 120 }],
  };
}
