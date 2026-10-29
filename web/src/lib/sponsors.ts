export type Sponsor = {
  id: string;
  name: string;
  text?: string | null;
  url: string;
  image?: string | null;
  active?: boolean;
  from?: string | null;
  to?: string | null;
};

export type Placement = {
  label?: string;
  mode?: "rotate" | "stack";
  rotateSeconds?: number;
  sponsors?: Sponsor[];
};

export type SponsorsConfig = {
  house?: { title?: string; text?: string; cta?: string; url?: string };
  placements?: Record<string, Placement>;
};

let cache: Promise<SponsorsConfig | null> | null = null;

export function loadSponsorsConfig(): Promise<SponsorsConfig | null> {
  if (cache) return cache;
  cache = fetch("/sponsors.json", { cache: "no-cache" })
    .then((res) => (res.ok ? (res.json() as Promise<SponsorsConfig>) : null))
    .catch(() => null);
  return cache;
}
