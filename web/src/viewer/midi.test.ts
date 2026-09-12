import { describe, expect, it } from "vitest";

import { parseMidi } from "./midi";

function midiBytes(): ArrayBuffer {
  // MThd (format 0, 1 track, 480 ticks/beat) + MTrk con tempo 120 y Do4 (60) y Sol4 (67).
  const bytes = [
    0x4d, 0x54, 0x68, 0x64, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x01, 0x01, 0xe0,
    0x4d, 0x54, 0x72, 0x6b, 0x00, 0x00, 0x00, 0x1e,
    0x00, 0xff, 0x51, 0x03, 0x07, 0xa1, 0x20, // tempo 500000us = 120bpm
    0x00, 0x90, 0x3c, 0x40, // note on Do4
    0x83, 0x60, 0x80, 0x3c, 0x40, // 480 ticks -> note off Do4
    0x00, 0x90, 0x43, 0x40, // Sol4
    0x83, 0x60, 0x80, 0x43, 0x40,
    0x00, 0xff, 0x2f, 0x00, // end of track
  ];
  return new Uint8Array(bytes).buffer;
}

describe("viewer/midi", () => {
  it("extrae notas y tempo de un SMF", () => {
    const seq = parseMidi(midiBytes());
    expect(seq).not.toBeNull();
    expect(seq?.notes).toHaveLength(2);
    expect(seq?.notes[0]).toMatchObject({ pitch: 60, startTime: 0, endTime: 0.5 });
    expect(seq?.notes[1]).toMatchObject({ pitch: 67, startTime: 0.5 });
    expect(seq?.tempos[0]?.qpm).toBe(120);
  });

  it("devuelve null si no es MIDI", () => {
    expect(parseMidi(new Uint8Array([1, 2, 3, 4]).buffer)).toBeNull();
  });
});
