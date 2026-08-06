import type { ReactNode } from "react";

export function EmptyState({ message = "Nothing here yet" }: { message?: string }): ReactNode {
  return (
    <div data-testid="empty" className="text-osap-muted">
      {message}
    </div>
  );
}
