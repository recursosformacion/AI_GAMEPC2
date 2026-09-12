import { describe, expect, it } from "vitest";

import { buildNoteSequence } from "./osmdSequence";

function fakeOsmd() {
  return {
    Sheet: {
      DefaultStartTempoInBpm: 120,
      SourceMeasures: [
        {
          Timestamp: { RealValue: 0 },
          Duration: { RealValue: 1 },
          VerticalSourceStaffEntryContainers: [
            {
              Timestamp: { RealValue: 0 },
              StaffEntries: [
                { VoiceEntries: [{ Notes: [{ Pitch: { halfTone: 48 }, Length: { RealValue: 0.25 } }] }] },
              ],
            },
          ],
        },
        {
          Timestamp: { RealValue: 1 },
          Duration: { RealValue: 1 },
          VerticalSourceStaffEntryContainers: [
            {
              Timestamp: { RealValue: 1 },
              StaffEntries: [
                { VoiceEntries: [{ Notes: [{ Pitch: { halfTone: 50 }, Length: { RealValue: 0.25 } }] }] },
              ],
            },
          ],
        },
      ],
    },
  };
}

describe("buildNoteSequence", () => {
  it("convierte redondas de OSMD a segundos (con tempo) y aplica el fix de octava", () => {
    const sequence = buildNoteSequence(fakeOsmd(), 120);
    expect(sequence).not.toBeNull();
    expect(sequence?.notes.map((n) => n.pitch)).toEqual([60, 62]);
    // quarter note a 120 bpm = 0.5 s; compás 2 empieza en redonda 1 -> 2 s.
    expect(sequence?.notes[0]?.startTime).toBeCloseTo(0, 6);
    expect(sequence?.notes[0]?.endTime).toBeCloseTo(0.5, 6);
    expect(sequence?.notes[1]?.startTime).toBeCloseTo(2, 6);
    expect(sequence?.totalTime).toBeCloseTo(4, 6);
  });

  it("devuelve null sin notas", () => {
    const empty = { Sheet: { SourceMeasures: [{ VerticalSourceStaffEntryContainers: [] }] } };
    expect(buildNoteSequence(empty, 100)).toBeNull();
  });
});
