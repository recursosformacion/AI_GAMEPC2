import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { SITE_URL, seoMetaForPath } from "./seoMeta";

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

/** Mantiene title, description, robots y canonical alineados con la ruta actual. */
export function useSeo(): void {
  const location = useLocation();
  useEffect(() => {
    const meta = seoMetaForPath(location.pathname, location.search);
    document.title = meta.title;
    upsertMeta("description", meta.description);
    upsertMeta("robots", meta.robots);
    upsertCanonical(`${SITE_URL}${meta.canonicalPath}`);
  }, [location.pathname, location.search]);
}
