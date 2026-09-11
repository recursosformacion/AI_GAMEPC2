import { describe, expect, it } from "vitest";

import { buildNoteSequence } from "./osmdSequence";

function fakeOsmd(notesPerStep: number[][], times: number[]) {
  let step = 0;
  const iterator = { EndReached: false, CurrentEnrolledTimestamp: { RealValue: times[0] ?? 0 } };
  const cursor = {
    Iterator: iterator,
    reset: () => {
      step = 0;
      iterator.EndReached = false;
      iterator.CurrentEnrolledTimestamp = { RealValue: times[0] ?? 0 };
    },
    next: () => {
      step += 1;
      if (step >= notesPerStep.length) {
        iterator.EndReached = true;
        return;
      }
      iterator.CurrentEnrolledTimestamp = { RealValue: times[step] ?? 0 };
    },
    NotesUnderCursor: () => (notesPerStep[step] ?? []).map((pitch) => ({ Pitch: { getHalfTone: () => pitch } })),
  };
  return { cursor };
}

describe("viewer/osmdSequence", () => {
  it("construye un NoteSequence desde el cursor de OSMD", () => {
    const osmd = fakeOsmd([[60, 64], [67]], [0, 0.5]);
    const sequence = buildNoteSequence(osmd, 100);
    expect(sequence).not.toBeNull();
    expect(sequence?.notes).toHaveLength(3);
    expect(sequence?.notes[0]).toMatchObject({ pitch: 60, startTime: 0, endTime: 0.5 });
    expect(sequence?.notes[2]).toMatchObject({ pitch: 67, startTime: 0.5 });
    expect(sequence?.tempos[0]).toEqual({ time: 0, qpm: 100 });
  });

  it("construye la secuencia desde el modelo de la partitura (medidas/voces)", () => {
    const osmd = {
      Sheet: {
        SourceMeasures: [
          {
            Timestamp: { RealValue: 0 },
            Duration: { RealValue: 0.5 },
            VerticalSourceStaffEntryContainers: [
              {
                Timestamp: { RealValue: 0 },
                StaffEntries: [
                  { VoiceEntries: [{ Notes: [{ Pitch: { getHalfTone: () => 60 }, Length: { RealValue: 0.25 } }] }] },
                ],
              },
              {
                Timestamp: { RealValue: 0.5 },
                StaffEntries: [
                  { VoiceEntries: [{ Notes: [{ Pitch: { getHalfTone: () => 67 }, Length: { RealValue: 0.25 } }] }] },
                ],
              },
            ],
          },
        ],
      },
    };
    const sequence = buildNoteSequence(osmd, 60);
    expect(sequence?.notes).toHaveLength(2);
    expect(sequence?.notes[0]).toMatchObject({ pitch: 60, startTime: 0, endTime: 1 });
    expect(sequence?.notes[1]).toMatchObject({ pitch: 67, startTime: 0.5 });
  });

  it("devuelve null si no hay cursor o notas", () => {
    expect(buildNoteSequence({}, 100)).toBeNull();
    expect(buildNoteSequence(fakeOsmd([[], []], [0, 1]), 100)).toBeNull();
  });
});
