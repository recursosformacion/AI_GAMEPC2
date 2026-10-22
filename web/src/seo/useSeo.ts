import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { LANGUAGES } from "../i18n/translations";
import { SITE_URL, seoMetaForPath } from "./seoMeta";

let ssrConsumed = false;

function upsertMeta(key: string, content: string): void {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[name="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute("name", key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function upsertCanonical(href: string): void {
  let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!link) {
    link = document.createElement("link");
    link.setAttribute("rel", "canonical");
    document.head.appendChild(link);
  }
  link.setAttribute("href", href);
}

/** hreflang para las variantes de idioma (?lang=) + x-default. Se limpia en noindex. */
function setHreflangs(path: string, indexable: boolean): void {
  document.head
    .querySelectorAll('link[rel="alternate"][hreflang]')
    .forEach((el) => el.remove());
  if (!indexable) return;
  const add = (hreflang: string, href: string) => {
    const link = document.createElement("link");
    link.setAttribute("rel", "alternate");
    link.setAttribute("hreflang", hreflang);
    link.setAttribute("href", href);
    document.head.appendChild(link);
  };
  for (const { code } of LANGUAGES) {
    add(code, `${SITE_URL}${path}?lang=${code}`);
  }
  add("x-default", `${SITE_URL}${path}`);
}

/** Mantiene title, description, robots, canonical y hreflang alineados con la ruta. */
export function useSeo(): void {
  const location = useLocation();
  useEffect(() => {
    // En la primera carga de una página SSR, los metadatos ya vienen del servidor con los
    // datos reales (nombre, biografía…). No sobrescribirlos con los genéricos de la SPA.
    if (!ssrConsumed && window.__OSAP_SSR_PATH__ === location.pathname) {
      ssrConsumed = true;
      return;
    }
    ssrConsumed = true;
    const meta = seoMetaForPath(location.pathname, location.search);
    document.title = meta.title;
    upsertMeta("description", meta.description);
    upsertMeta("robots", meta.robots);
    upsertCanonical(`${SITE_URL}${meta.canonicalPath}`);
    setHreflangs(meta.canonicalPath, meta.robots.includes("index"));
  }, [location.pathname, location.search]);
}
