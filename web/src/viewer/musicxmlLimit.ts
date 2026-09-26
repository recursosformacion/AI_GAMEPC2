// Recorta un MusicXML a un RANGO de compases por parte [start, start+count).
//
// Motivo: algunas transcripciones OMR son larguísimas (cientos de compases); OSMD tarda
// decenas de segundos en maquetarlas. El visor muestra por páginas para abrir rápido, y
// permite forzar la partitura completa con `?measures=all`.

export interface LimitResult {
  xml: string;
  truncated: boolean;
  total: number;
  kept: number;
  start: number;
}

export function limitMeasures(xml: string, start: number, count: number): LimitResult {
  const from = Math.max(start, 0);
  if (count <= 0) return { xml, truncated: false, total: 0, kept: 0, start: from };
  try {
    const doc = new DOMParser().parseFromString(xml, "application/xml");
    if (doc.getElementsByTagName("parsererror").length > 0) {
      return { xml, truncated: false, total: 0, kept: 0, start: from };
    }
    const parts = Array.from(doc.getElementsByTagName("part"));
    let total = 0;
    for (const part of parts) {
      const measures = Array.from(part.childNodes).filter(
        (n): n is Element => n.nodeType === 1 && (n as Element).tagName === "measure"
      );
      total = Math.max(total, measures.length);
      measures.forEach((measure, index) => {
        if (index < from || index >= from + count) measure.parentNode?.removeChild(measure);
      });
    }
    const kept = Math.max(Math.min(count, Math.max(total - from, 0)), 0);
    if (from === 0 && total <= count) {
      return { xml, truncated: false, total, kept: total, start: 0 };
    }
    return { xml: new XMLSerializer().serializeToString(doc), truncated: true, total, kept, start: from };
  } catch {
    return { xml, truncated: false, total: 0, kept: 0, start: from };
  }
}
