import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>): ReactNode {
  return (
    <button
      className={`rounded bg-osap-accent px-4 py-2 text-white transition-colors hover:bg-osap-accent/90 disabled:opacity-50 ${className ?? ""}`}
      {...props}
    >
      {children}
    </button>
  );
}
