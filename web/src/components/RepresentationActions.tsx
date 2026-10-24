import type { RepresentationLike } from "../lib/representations";
import { getRepresentationActions } from "../lib/representations";

interface Labels {
  view: string;
  download: string;
  open: string;
}

interface RepresentationActionsProps {
  representation: RepresentationLike;
  workTitle?: string | null;
  variant?: "icons" | "buttons";
  showWeb?: boolean;
  labels?: Partial<Labels>;
}

function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M4 21h16" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 4h6v6" /><path d="M20 4 10 14" /><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
    </svg>
  );
}

export function RepresentationActions({
  representation,
  workTitle,
  variant = "buttons",
  showWeb = true,
  labels,
}: RepresentationActionsProps) {
  const actions = getRepresentationActions(representation, workTitle);
  if (!actions.canView && !actions.canDownload && !(showWeb && (actions.webHref || actions.externalHref))) {
    return null;
  }

  const text: Labels = {
    view: labels?.view ?? "Ver",
    download: labels?.download ?? "Descargar",
    open: (labels?.open ?? "Abrir en {p}").replace("{p}", representation.provider),
  };
  const openHref = variant === "icons" ? actions.webHref : actions.externalHref;
  const external = actions.externalHref;

  if (variant === "icons") {
    const iconClass =
      "inline-flex h-9 w-9 items-center justify-center rounded border border-osap-border-strong text-osap-accent hover:bg-osap-accent-soft";
    return (
      <span className="flex shrink-0 items-center gap-1">
        {actions.canView && actions.viewHref ? (
          <a href={actions.viewHref} target="_blank" rel="noopener noreferrer" aria-label={text.view} title={text.view} className={iconClass}>
            <EyeIcon />
          </a>
        ) : null}
        {actions.canDownload && actions.downloadHref ? (
          <a href={actions.downloadHref} download target="_blank" rel="noopener noreferrer" aria-label={text.download} title={text.download} className={iconClass}>
            <DownloadIcon />
          </a>
        ) : null}
        {showWeb && openHref ? (
          <a href={openHref} target="_blank" rel="noopener noreferrer" aria-label={text.open} title={text.open} className={iconClass}>
            <ExternalIcon />
          </a>
        ) : null}
      </span>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {actions.canView && actions.viewHref ? (
        <a href={actions.viewHref} target="_blank" rel="noreferrer" className="rounded bg-osap-accent px-3 py-1.5 text-sm text-white">
          {text.view}
        </a>
      ) : null}
      {actions.canDownload && actions.downloadHref ? (
        <a href={actions.downloadHref} download target="_blank" rel="noreferrer" className="rounded border border-osap-accent px-3 py-1.5 text-sm text-osap-accent">
          {text.download}
        </a>
      ) : null}
      {showWeb && external ? (
        <a href={external} target="_blank" rel="noreferrer" className="rounded border border-osap-accent px-3 py-1.5 text-sm text-osap-accent">
          {text.open}
        </a>
      ) : null}
    </div>
  );
}


