import type { ReactNode } from "react";

export function Card({ title, children }: { title?: string; children: ReactNode }): ReactNode {
  return (
    <section className="rounded-lg border border-osap-border bg-osap-surface p-4 shadow-sm">
      {title ? <h2 className="mb-2 font-semibold text-osap-ink">{title}</h2> : null}
      {children}
    </section>
  );
}
