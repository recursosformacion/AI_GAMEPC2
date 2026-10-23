import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

type Sponsor = {
  id: string;
  name: string;
  text?: string | null;
  url: string;
  image?: string | null;
  active?: boolean;
  from?: string | null;
  to?: string | null;
};

type Placement = {
  label?: string;
  mode?: "rotate" | "stack";
  rotateSeconds?: number;
  sponsors?: Sponsor[];
};

type SponsorsConfig = {
  house?: { title?: string; text?: string; cta?: string; url?: string };
  placements?: Record<string, Placement>;
};

const FALLBACK_HOUSE = {
  title: "Espacio para anunciantes y patrocinadores",
  text: "¿Tienes una tienda de partituras, una editorial, un coro, un festival o un proyecto musical? Este espacio puede ser tuyo.",
  cta: "Contacta con nosotros",
  url: "/corrections?kind=contact",
};

let cache: Promise<SponsorsConfig | null> | null = null;

function loadConfig(): Promise<SponsorsConfig | null> {
  if (cache) return cache;
  cache = fetch("/sponsors.json", { cache: "no-cache" })
    .then((res) => (res.ok ? (res.json() as Promise<SponsorsConfig>) : null))
    .catch(() => null);
  return cache;
}

function isActive(sponsor: Sponsor, now: Date): boolean {
  if (sponsor.active === false) return false;
  const day = now.toISOString().slice(0, 10);
  if (sponsor.from && sponsor.from > day) return false;
  if (sponsor.to && sponsor.to < day) return false;
  return true;
}

function House({ house }: { house: NonNullable<SponsorsConfig["house"]> }) {
  return (
    <aside
      className="rounded-lg border border-dashed border-osap-border bg-osap-surface/70 p-4"
      aria-label="Espacio para anunciantes"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-muted">Publicidad</p>
      <p className="mt-1 font-display text-lg font-semibold text-osap-ink">{house.title}</p>
      <p className="mt-1 max-w-2xl text-sm text-osap-muted">{house.text}</p>
      <Link to={house.url ?? FALLBACK_HOUSE.url} className="mt-2 inline-block text-sm font-semibold text-osap-accent hover:underline">
        {house.cta ?? FALLBACK_HOUSE.cta} →
      </Link>
    </aside>
  );
}

export function SponsorSlot({ placement }: { placement: string }) {
  const [config, setConfig] = useState<SponsorsConfig | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    let alive = true;
    void loadConfig().then((data) => {
      if (alive) setConfig(data);
    });
    return () => {
      alive = false;
    };
  }, []);

  const slot = config?.placements?.[placement];
  const now = new Date();
  const sponsors = (slot?.sponsors ?? []).filter((s) => s && s.name && s.url && isActive(s, now));
  const mode = slot?.mode ?? "rotate";
  const rotateMs = Math.max(3, slot?.rotateSeconds ?? 8) * 1000;

  useEffect(() => {
    if (mode !== "rotate" || sponsors.length < 2) return;
    const id = window.setInterval(() => setIndex((i) => (i + 1) % sponsors.length), rotateMs);
    return () => window.clearInterval(id);
  }, [mode, rotateMs, sponsors.length]);

  if (!slot || sponsors.length === 0) {
    return <House house={config?.house ?? FALLBACK_HOUSE} />;
  }

  const current = sponsors[index] ?? sponsors[0];
  const visible = mode === "stack" ? sponsors : current ? [current] : [];
  return (
    <aside className="rounded-lg border border-osap-border bg-osap-surface p-4" aria-label="Patrocinadores">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-muted">
        {slot.label ?? "Patrocinado por"}
      </p>
      <div className={mode === "stack" ? "mt-2 space-y-3" : "mt-2"}>
        {visible.map((sponsor) => (
          <div key={sponsor.id} className="flex items-start gap-3">
            {sponsor.image ? (
              <img src={sponsor.image} alt="" className="h-12 w-12 shrink-0 rounded object-cover" loading="lazy" />
            ) : (
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-osap-accent-soft font-display text-sm font-semibold text-osap-accent">
                {sponsor.name.slice(0, 2).toUpperCase()}
              </span>
            )}
            <div className="min-w-0">
              <p className="font-display text-lg font-semibold text-osap-ink">{sponsor.name}</p>
              {sponsor.text ? <p className="mt-0.5 text-sm text-osap-muted">{sponsor.text}</p> : null}
              <a
                href={sponsor.url}
                target="_blank"
                rel="sponsored noopener noreferrer"
                className="mt-1 inline-block text-sm font-semibold text-osap-accent hover:underline"
              >
                Más información →
              </a>
            </div>
          </div>
        ))}
      </div>
      {mode === "rotate" && sponsors.length > 1 ? (
        <div className="mt-2 flex gap-1" aria-label="Más patrocinadores">
          {sponsors.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Ver ${s.name}`}
              className={`h-1.5 w-4 rounded-full ${i === index ? "bg-osap-accent" : "bg-osap-border"}`}
            />
          ))}
        </div>
      ) : null}
    </aside>
  );
}
