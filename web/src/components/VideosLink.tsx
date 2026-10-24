import type { MouseEvent } from "react";
import { useAuth } from "../state/auth";
import { videosUrl } from "../lib/videos";

function VideosIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M21.6 7.2a2.5 2.5 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4a2.5 2.5 0 0 0-1.8 1.8C2 8.8 2 12 2 12s0 3.2.4 4.8a2.5 2.5 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8C22 15.2 22 12 22 12s0-3.2-.4-4.8ZM10 15.5v-7l6 3.5-6 3.5Z" />
    </svg>
  );
}

interface VideosLinkProps {
  workId?: string | null;
  title?: string | null;
  composer?: string | null;
  resourceId?: string | null;
  variant?: "button" | "icon" | "compact";
  label?: string;
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
}

export function VideosLink({
  workId,
  title,
  composer,
  resourceId,
  variant = "button",
  label = "Vídeos",
  onClick,
}: VideosLinkProps) {
  const token = useAuth((s) => s.accessToken);
  const href = videosUrl({ workId, title, composer, resourceId, token });
  if (!href) return null;

  if (variant === "icon") {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={label}
        title={label}
        onClick={onClick}
        className="inline-flex h-9 w-9 items-center justify-center rounded border border-osap-border-strong text-osap-accent hover:bg-osap-accent-soft"
      >
        <VideosIcon />
      </a>
    );
  }

  if (variant === "compact") {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={label}
        onClick={onClick}
        className="inline-flex shrink-0 items-center gap-1 rounded border border-osap-border px-2 py-1 text-xs font-medium text-osap-accent hover:bg-osap-accent-soft"
      >
        <VideosIcon size={13} />
        {label}
      </a>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded border border-osap-border-strong px-3 py-1.5 text-sm font-semibold text-osap-accent hover:bg-osap-accent-soft"
    >
      <VideosIcon />
      {label}
    </a>
  );
}

