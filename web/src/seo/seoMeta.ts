// Fase 1 SEO (SPA): metadatos por ruta (title/description/robots) y canonical.
// Las páginas de entidad (/obra, /compositor) las sirve osap-api con HTML real; aquí
// solo se gestionan las rutas de la SPA, marcando como noindex las herramientas internas.

export const SITE_URL = "https://app.openmusicrepository.com";

const DEFAULT_TITLE = "OSAP — OpenMusicRepository";
const DEFAULT_DESCRIPTION =
  "OpenMusicRepository — partituras musicales de dominio público con buscador por obra, compositor y catálogo (KV, BWV, Op.…).";

export interface SeoMeta {
  title: string;
  description: string;
  robots: string;
  canonicalPath: string;
}

const ROUTE_META: Record<string, { title: string; description: string }> = {
  "/": { title: DEFAULT_TITLE, description: DEFAULT_DESCRIPTION },
  "/explore": {
    title: "Explorar el catálogo | OpenMusicRepository",
    description: "Explora obras, compositores y catálogos musicales de dominio público en OpenMusicRepository.",
  },
  "/composers": {
    title: "Compositores — obras y partituras | OpenMusicRepository",
    description:
      "Listado de compositores con sus obras y partituras disponibles en OpenMusicRepository.",
  },
  "/discover": {
    title: "Descubrir fuentes musicales | OpenMusicRepository",
    description: "Fuentes y catálogos musicales integrados en OpenMusicRepository.",
  },
  "/catalog": {
    title: "Catálogo de obras | OpenMusicRepository",
    description: "Catálogo de obras musicales de dominio público con sus recursos disponibles.",
  },
  "/sources": {
    title: "Fuentes | OpenMusicRepository",
    description: "Proveedores y fuentes de partituras integrados en OpenMusicRepository.",
  },
  "/about": {
    title: "Acerca de OSAP | OpenMusicRepository",
    description: "Qué es OSAP y OpenMusicRepository: catálogo abierto de partituras de dominio público.",
  },
  "/about/how-it-works": {
    title: "Cómo funciona | OpenMusicRepository",
    description: "Cómo OSAP localiza, resuelve y ofrece partituras de dominio público.",
  },
  "/support": {
    title: "Apoyar el proyecto | OpenMusicRepository",
    description: "Apoya el mantenimiento y crecimiento de OpenMusicRepository.",
  },
  "/collaborators": {
    title: "Colaboradores | OpenMusicRepository",
    description: "Personas y entidades que colaboran con OpenMusicRepository.",
  },
};

// Herramientas internas o resultados de búsqueda: nunca deben indexarse.
// Se compara por segmento (no por prefijo de cadena) para que /composer y /composers
// no se confundan entre sí.
const NOINDEX_ROUTES = [
  "/studio",
  "/composer",
  "/admin",
  "/viewer",
  "/resolution",
  "/candidates",
  "/jobs",
  "/knowledge",
  "/providers",
  "/oidc",
  "/corrections",
];

const SORTED_ROUTE_KEYS = Object.keys(ROUTE_META).sort((a, b) => b.length - a.length);

function canonicalPathFor(pathname: string): string {
  if (pathname === "" || pathname === "/") return "/";
  return pathname.replace(/\/+$/, "");
}

function isNoindex(pathname: string, search: string): boolean {
  const matchesSegment = NOINDEX_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
  // Búsquedas con parámetros (?q=…): resultado, no contenido canónico.
  const isQuery = /[?&]q=/.test(search);
  return matchesSegment || isQuery;
}

export function seoMetaForPath(pathname: string, search = ""): SeoMeta {
  const canonicalPath = canonicalPathFor(pathname);
  const key =
    SORTED_ROUTE_KEYS.find((route) => canonicalPath === route) ??
    SORTED_ROUTE_KEYS.find((route) => canonicalPath.startsWith(`${route}/`));
  const base = key ? ROUTE_META[key] : undefined;
  return {
    title: base?.title ?? DEFAULT_TITLE,
    description: base?.description ?? DEFAULT_DESCRIPTION,
    robots: isNoindex(pathname, search) ? "noindex, nofollow" : "index, follow",
    canonicalPath,
  };
}
