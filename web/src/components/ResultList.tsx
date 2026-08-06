import type { ReactNode } from "react";

export function ResultList<T>({
  items,
  keyOf,
  renderItem,
}: {
  items: T[];
  keyOf: (item: T) => string;
  renderItem: (item: T) => ReactNode;
}): ReactNode {
  return (
    <ul data-testid="result-list" className="divide-y divide-osap-border">
      {items.map((item) => (
        <li key={keyOf(item)} className="py-2">
          {renderItem(item)}
        </li>
      ))}
    </ul>
  );
}
