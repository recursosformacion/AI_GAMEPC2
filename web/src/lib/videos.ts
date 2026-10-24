export function videosBaseUrl(): string | null {
  const configured = import.meta.env.VITE_VIDEOS_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return "http://localhost:8400";
}

export function videosUrl({
  workId,
  title,
  composer,
  resourceId,
  token,
}: {
  workId?: string | null;
  title?: string | null;
  composer?: string | null;
  resourceId?: string | null;
  token?: string | null;
}): string | null {
  const base = videosBaseUrl();
  if (!base || !workId) return null;
  const params = new URLSearchParams();
  if (resourceId) params.set("resource", resourceId);
  if (title) params.set("title", title);
  if (composer) params.set("composer", composer);
  if (token) params.set("token", token);
  return `${base}/works/${encodeURIComponent(workId)}?${params.toString()}`;
}
