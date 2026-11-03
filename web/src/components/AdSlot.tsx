import { useEffect, useRef, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import { SponsorSlot } from "./SponsorSlot";

type AdSlotProps = {
  placement: string;
  pageType: string;
  entityType?: string;
  entityId?: string;
  fallbackPlacement: string;
  className?: string;
  minHeight?: number;
};

/**
 * Reserva un área real y deja que ai_publicidad elija la composición que cabe.
 * El HTML ya viene escapado y compuesto por el servicio; React solo lo inserta.
 */
export function AdSlot({
  placement,
  pageType,
  entityType,
  entityId,
  fallbackPlacement,
  className = "",
  minHeight = 180,
}: AdSlotProps) {
  const { lang } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const [area, setArea] = useState({ width: 0, height: minHeight });
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      setArea({
        width: Math.max(0, Math.round(rect.width)),
        height: Math.max(minHeight, Math.round(rect.height)),
      });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [minHeight]);

  useEffect(() => {
    if (area.width < 160 || area.height < 50) {
      setFailed(true);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void apiClient
        .composeAd({
          application: "osap",
          page: {
            type: pageType,
            entity_type: entityType ?? null,
            entity_id: entityId ?? null,
            language: lang,
          },
          placement,
          device: window.innerWidth < 640 ? "mobile" : "desktop",
          mode: "auto_area",
          area: { width: Math.min(area.width, 2000), height: Math.min(area.height, 1200) },
          max_ads: 3,
          gap: 12,
          orientation: "auto",
        })
        .then((fragment) => {
          if (cancelled) return;
          if (!fragment || fragment.includes('data-layout-status="no-fill"')) {
            setFailed(true);
            setHtml(null);
            return;
          }
          setHtml(fragment);
          setFailed(false);
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [area.width, area.height, pageType, entityType, entityId, placement, lang]);

  return (
    <div ref={ref} className={className} style={{ minHeight }}>
      {html && !failed ? (
        <div dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <SponsorSlot placement={fallbackPlacement} />
      )}
    </div>
  );
}
