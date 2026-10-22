// Resumen: servidor SSR de las páginas públicas (compositores y obras). Renderiza la app
// React en servidor, inyecta metadatos y estado inicial, y cachea el HTML. Apache/nginx le
// envían solo las rutas públicas; el resto sigue siendo la SPA estática.
//
// Uso: node ssr/server.mjs
// Variables: OSAP_API_ORIGIN (def. http://127.0.0.1:8001), OSAP_SSR_PORT (3000),
// OSAP_PUBLIC_ORIGIN (def. http://osap-app), OSAP_SSR_DEV=1 (sin caché), OSAP_SSR_TTL (60),
// OSAP_SSR_STALE (600).

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = process.env.OSAP_WEB_DIST ?? join(__dirname, "..", "dist");
const SSR_ENTRY = process.env.OSAP_SSR_ENTRY ?? join(__dirname, "..", "dist-ssr", "entry-server.js");
const API = (process.env.OSAP_API_ORIGIN ?? "http://127.0.0.1:8001").replace(/\/+$/, "");
const PORT = Number(process.env.OSAP_SSR_PORT ?? 3000);
const PUBLIC_ORIGIN = (process.env.OSAP_PUBLIC_ORIGIN ?? "http://osap-app").replace(/\/+$/, "");
const DEV = process.env.OSAP_SSR_DEV === "1" || process.env.NODE_ENV !== "production";
const TTL_MS = Number(process.env.OSAP_SSR_TTL ?? 60) * 1000;
const STALE_MS = Number(process.env.OSAP_SSR_STALE ?? 600) * 1000;

const { render } = await import(pathToFileURL(SSR_ENTRY).href);
const template = await readFile(join(DIST, "index.html"), "utf8");

const LANGS = new Set(["es", "ca", "fr", "en", "de"]);
const cache = new Map();
const inflight = new Map();

function languageFrom(req, requestUrl) {
  // Prioridad: ?lang explícito > cookie de preferencia > español (idioma del sitio).
  // No se usa Accept-Language: si el navegador está en inglés, Chrome auto-traduce la
  // página y destrozaba las iniciales de los avatares («AD» → «ANUNCIO», «AK» → «Alaska»).
  try {
    const fromQuery = new URL(requestUrl, "http://localhost").searchParams.get("lang");
    if (fromQuery && LANGS.has(fromQuery)) return fromQuery;
  } catch {
    // URL inválida: se ignora
  }
  const cookie = /(?:^|;\s*)osap\.lang=(es|ca|fr|en|de)/.exec(req.headers.cookie ?? "");
  if (cookie) return cookie[1];
  return "es";
}

function darkFrom(req) {
  return /(?:^|;\s*)osap\.theme=dark/.test(req.headers.cookie ?? "");
}

async function apiGet(path) {
  try {
    const res = await fetch(`${API}/api/v1${path}`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) return { ok: false, status: res.status, data: null };
    const body = await res.json();
    if (body?.success !== true || body.data === undefined) {
      return { ok: false, status: 502, data: null };
    }
    return { ok: true, status: 200, data: body.data };
  } catch {
    return { ok: false, status: 503, data: null };
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function safeJson(value) {
  return JSON.stringify(value).replace(/</g, "\\u003c").replace(/\u2028|\u2029/g, "");
}

function years(birth, death) {
  const b = String(birth ?? "").trim();
  const d = String(death ?? "").trim();
  if (b && d) return `${b}–${d}`;
  if (b) return `${b}–`;
  return d ? `–${d}` : "";
}

function truncate(text, max = 300) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}

async function prefetch(pathname, searchParams) {
  const health = await apiGet("/system/health");
  const state = {
    system: health.ok ? { health: health.data } : undefined,
    composers: undefined,
    publicWork: undefined,
    meta: null,
    status: 200,
  };

  if (pathname === "/composers") {
    const q = (searchParams.get("q") ?? "").trim();
    const query = new URLSearchParams({ limit: "30", offset: "0", visible: "visible" });
    if (q) query.set("q", q);
    const list = await apiGet(`/composers?${query.toString()}`);
    if (!list.ok) return { ...state, degraded: true };
    state.composers = { list: list.data, q, lastQuery: q, lastOffset: 0 };
    state.meta = {
      title: q
        ? `Compositores: ${q} | OpenMusicRepository`
        : "Compositores — obras y partituras | OpenMusicRepository",
      description:
        "Listado de compositores con sus obras y partituras disponibles en OpenMusicRepository.",
      canonical: `${PUBLIC_ORIGIN}/composers`,
      robots: q ? "noindex, follow" : "index, follow",
    };
    return state;
  }

  const person = /^\/composers\/([^/]+)(?:\/[^/]+)?\/?$/.exec(pathname);
  if (person) {
    const id = decodeURIComponent(person[1]);
    const [biography, works, indexWorks] = await Promise.all([
      apiGet(`/composers/${encodeURIComponent(id)}/biography`),
      apiGet(`/composers/${encodeURIComponent(id)}/works?limit=200&offset=0`),
      apiGet(`/composers/${encodeURIComponent(id)}/index-works?limit=300&offset=0`),
    ]);
    if (!biography.ok) return { ...state, degraded: biography.status >= 500, status: biography.status };
    state.composers = {
      biography: biography.data,
      works: works.ok ? works.data : { items: [], total: 0 },
      worksFor: id,
      indexWorks: indexWorks.ok ? indexWorks.data : undefined,
      indexWorksFor: id,
    };
    const name = String(biography.data?.name ?? "Compositor");
    const period = years(biography.data?.birth_year, biography.data?.death_year);
    state.meta = {
      title: `${name}${period ? ` (${period})` : ""} — Obras y partituras | OpenMusicRepository`,
      description:
        truncate(biography.data?.biography_summary) ||
        `Obras y partituras de ${name} en OpenMusicRepository.`,
      canonical: `${PUBLIC_ORIGIN}${pathname}`,
      robots: "index, follow",
      jsonLd: {
        "@context": "https://schema.org",
        "@type": "Person",
        name,
        jobTitle: "Compositor",
        url: `${PUBLIC_ORIGIN}${pathname}`,
        ...(period ? { birthDate: biography.data?.birth_year ?? undefined } : {}),
        ...(biography.data?.death_year ? { deathDate: biography.data.death_year } : {}),
        ...(biography.data?.biography_nationality
          ? { nationality: biography.data.biography_nationality }
          : {}),
      },
    };
    return state;
  }

  const work = /^\/obras\/([^/]+)(?:\/[^/]+)?\/?$/.exec(pathname);
  if (work) {
    const raw = decodeURIComponent(work[1]);
    const id = raw.startsWith("index-") ? raw : `index-${raw}`;
    const sheet = await apiGet(`/works/public/${encodeURIComponent(id)}`);
    if (!sheet.ok) {
      return {
        ...state,
        publicWork: { sheet: null, status: sheet.status === 404 ? "missing" : "loading" },
        status: sheet.status === 404 ? 404 : 503,
        degraded: sheet.status >= 500,
      };
    }
    state.publicWork = { sheet: sheet.data, status: "ok" };
    const title = String(sheet.data?.work?.title ?? "Obra");
    const composer = sheet.data?.work?.composer ? ` de ${sheet.data.work.composer}` : "";
    const catalogue = sheet.data?.work?.catalogue ? ` (${sheet.data.work.catalogue})` : "";
    state.meta = {
      title: `${title}${catalogue}${composer} — Partituras | OpenMusicRepository`,
      description: truncate(
        `${title}${composer}${catalogue}: representaciones y partituras disponibles en OpenMusicRepository.`,
      ),
      canonical: `${PUBLIC_ORIGIN}${pathname}`,
      robots: "index, follow",
      jsonLd: {
        "@context": "https://schema.org",
        "@type": "MusicComposition",
        name: title,
        url: `${PUBLIC_ORIGIN}${pathname}`,
        ...(sheet.data?.work?.composer ? { composer: { "@type": "Person", name: sheet.data.work.composer } } : {}),
        ...(sheet.data?.work?.catalogue ? { catalogNumber: sheet.data.work.catalogue } : {}),
      },
    };
    return state;
  }

  return null;
}

function inject(html, state, lang, dark) {
  const meta = state.meta ?? {};
  let out = template;
  out = out.replace(/<html lang="[^"]*"/, `<html lang="${lang}"${dark ? ' data-theme="dark"' : ""}`);
  out = out.replace(/<title>[\s\S]*?<\/title>/, `<title>${escapeHtml(meta.title ?? "OSAP — OpenMusicRepository")}</title>`);
  out = out.replace(
    /<meta name="description" content="[^"]*"\s*\/?>/,
    `<meta name="description" content="${escapeHtml(meta.description ?? "")}" />`,
  );
  const head = [
    meta.canonical ? `<link rel="canonical" href="${escapeHtml(meta.canonical)}" />` : "",
    meta.robots ? `<meta name="robots" content="${escapeHtml(meta.robots)}" />` : "",
    meta.jsonLd ? `<script type="application/ld+json">${safeJson(meta.jsonLd)}</script>` : "",
  ]
    .filter(Boolean)
    .join("\n    ");
  if (head) out = out.replace("</head>", `    ${head}\n  </head>`);
  const initialState = {
    lang,
    dark,
    composers: state.composers,
    system: state.system,
    publicWork: state.publicWork,
  };
  const payload = `<script>window.__OSAP_STATE__=${safeJson(initialState)};window.__OSAP_SSR_PATH__=${safeJson(
    meta.canonicalPath ?? "",
  )};</script>`;
  out = out.replace(
    '<div id="root"></div>',
    `<div id="root">${html}</div>${payload}`,
  );
  return out;
}

async function buildPage(url, lang, dark) {
  const parsed = new URL(url, PUBLIC_ORIGIN);
  const state = await prefetch(parsed.pathname, parsed.searchParams);
  if (state === null) return null;
  if (state.degraded) return null;
  const html = await render(parsed.pathname + parsed.search, {
    lang,
    dark,
    composers: state.composers,
    system: state.system,
    publicWork: state.publicWork,
  });
  return {
    status: state.status,
    html: inject(
      html,
      { ...state, meta: { ...state.meta, canonicalPath: parsed.pathname } },
      lang,
      dark,
    ),
  };
}

function cacheKey(req, url) {
  return `${languageFrom(req, url)}|${darkFrom(req) ? "dark" : "light"}|${url}`;
}

function cached(key, build) {
  if (DEV) return build();
  const hit = cache.get(key);
  const now = Date.now();
  if (hit) {
    const age = now - hit.at;
    if (age < TTL_MS) return hit.promise;
    if (age < TTL_MS + STALE_MS) {
      if (!hit.revalidating) {
        hit.revalidating = true;
        void build()
          .then((fresh) => cache.set(key, { at: Date.now(), promise: Promise.resolve(fresh) }))
          .catch(() => {})
          .finally(() => {
            hit.revalidating = false;
          });
      }
      return hit.promise;
    }
  }
  const promise = build().then((result) => {
    cache.set(key, { at: Date.now(), promise: Promise.resolve(result) });
    if (cache.size > 800) {
      const oldest = cache.keys().next().value;
      if (oldest !== undefined) cache.delete(oldest);
    }
    return result;
  });
  cache.set(key, { at: now, promise });
  void promise.catch(() => cache.delete(key));
  return promise;
}

const server = createServer(async (req, res) => {
  const url = req.url ?? "/";
  const pathname = new URL(url, "http://localhost").pathname;
  if (pathname === "/health") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }
  const isPublic =
    pathname === "/composers" ||
    /^\/composers\/[^/]+(?:\/[^/]+)?\/?$/.test(pathname) ||
    /^\/obras\/[^/]+(?:\/[^/]+)?\/?$/.test(pathname);
  if (!isPublic) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("not found");
    return;
  }

  const key = cacheKey(req, pathname + new URL(url, "http://localhost").search);
  const lang = languageFrom(req, url);
  const dark = darkFrom(req);
  try {
    let pending = inflight.get(key);
    if (!pending) {
      pending = cached(key, () => buildPage(url, lang, dark));
      inflight.set(key, pending);
      void pending.finally(() => inflight.delete(key));
    }
    const page = await pending;
    if (page === null) {
      const spa = template;
      res.writeHead(200, {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
      });
      res.end(spa);
      return;
    }
    res.writeHead(page.status, {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": DEV
        ? "no-store, no-cache, must-revalidate"
        : "public, s-maxage=60, stale-while-revalidate=600",
      Vary: "Accept-Language, Cookie",
    });
    res.end(page.html);
  } catch (error) {
    console.error("SSR error", error);
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" });
    res.end("SSR error");
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`SSR escuchando en http://127.0.0.1:${PORT} (api ${API}, dev=${DEV})`);
});
