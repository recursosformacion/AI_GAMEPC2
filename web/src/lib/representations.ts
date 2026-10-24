export interface RepresentationLike {
  id?: string | null;
  provider: string;
  format: string;
  url?: string | null;
  downloadable?: boolean;
  available?: boolean;
}

const STORAGE_HOSTS = ["storage.openmusicrepository.com", "127.0.0.1", "localhost", "osap-storage"];
const VIEW_FORMATS = new Set(["musicxml", "mxl", "xml", "mei", "pdf"]);

export function isStorageUrl(url?: string | null): boolean {
  if (!url) return false;
  if (url.startsWith("/api/download/") || url.startsWith("/api/v1/representations/")) return true;
  try {
    const base = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    return STORAGE_HOSTS.includes(new URL(url, base).hostname);
  } catch {
    return false;
  }
}

export function representationViewHref(
  id?: string | null,
  format?: string | null,
  workTitle?: string | null,
): string | null {
  if (!id) return null;
  const fmt = (format ?? "").toLowerCase();
  const title = workTitle ? `&title=${encodeURIComponent(workTitle)}` : "";
  if (fmt === "midi") {
    return `/viewer?rep=${encodeURIComponent(id)}&format=midi${title}`;
  }
  if (VIEW_FORMATS.has(fmt)) {
    return `/viewer?rep=${encodeURIComponent(id)}${title}`;
  }
  return `/api/v1/representations/${encodeURIComponent(id)}/download?view=1`;
}

export interface RepresentationActionState {
  isOmr: boolean;
  externalHref: string | null;
  webHref: string | null;
  viewHref: string | null;
  downloadHref: string | null;
  canView: boolean;
  canDownload: boolean;
}

export function getRepresentationActions(
  representation: RepresentationLike,
  workTitle?: string | null,
): RepresentationActionState {
  const id = representation.id?.trim() ?? "";
  const provider = representation.provider ?? "";
  const isOmr = provider.toLowerCase() === "omr";
  const externalHref = representation.url && !isStorageUrl(representation.url) ? representation.url : null;
  const localAccess =
    representation.downloadable === true || (externalHref === null && representation.available !== false);
  const canOpen = Boolean(id) && (isOmr || localAccess);
  return {
    isOmr,
    externalHref,
    webHref: representation.url ?? null,
    viewHref: canOpen ? representationViewHref(id, representation.format, workTitle) : null,
    downloadHref: canOpen
      ? `/api/v1/representations/${encodeURIComponent(id)}/download`
      : null,
    canView: canOpen,
    canDownload: canOpen,
  };
}

