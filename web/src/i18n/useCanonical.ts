import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const SITE = "https://app.openmusicrepository.com";

/** Actualiza el <link rel="canonical"> con la URL canónica de la ruta actual (SEO). */
export function useCanonical() {
  const location = useLocation();
  useEffect(() => {
    let link = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.setAttribute("rel", "canonical");
      document.head.appendChild(link);
    }
    const path = location.pathname === "/" ? "" : location.pathname;
    link.setAttribute("href", `${SITE}${path}`);
  }, [location.pathname]);
}
