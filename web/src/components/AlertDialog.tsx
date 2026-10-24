import { useEffect, useRef } from "react";

interface AlertDialogProps {
  open: boolean;
  title: string;
  message: string;
  closeLabel: string;
  onClose: () => void;
}

export function AlertDialog({ open, title, message, closeLabel, onClose }: AlertDialogProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-message"
        className="w-full max-w-md rounded-card border border-osap-border bg-osap-surface p-5 shadow-xl"
      >
        <h2 id="alert-dialog-title" className="text-base font-semibold text-osap-ink">
          {title}
        </h2>
        <p id="alert-dialog-message" className="mt-2 text-sm text-osap-muted">
          {message}
        </p>
        <div className="mt-5 flex justify-end">
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white"
          >
            {closeLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
