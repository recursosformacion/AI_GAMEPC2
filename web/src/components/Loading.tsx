import type { ReactNode } from "react";

export function Loading({ label = "Loading" }: { label?: string }): ReactNode {
  return (
    <div data-testid="loading" className="text-osap-muted">
      {label}…
    </div>
  );
}
