import type { ReactNode } from "react";
import type { EvidenceInfo } from "../api/types";

export function EvidenceView({ items }: { items: EvidenceInfo[] }): ReactNode {
  return (
    <ul data-testid="evidence">
      {items.map((item, index) => (
        <li key={index}>
          {item.source}: {item.code} ({item.score})
        </li>
      ))}
    </ul>
  );
}
