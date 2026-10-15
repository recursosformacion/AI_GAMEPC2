import { useState } from "react";
import { useI18n } from "../i18n/I18n";

// Enlaces de «compartir» reutilizables (mismos destinos que la página SSR del artículo/coral).
// Instagram no ofrece una intención web para compartir enlaces: se cubre con «Copiar enlace»
// y con la hoja nativa del sistema (`navigator.share`), que sí lo incluye en móvil/escritorio.
export interface ShareTarget {
  key: string;
  label: string;
  href: string;
}

export function shareTargets(url: string, title: string): ShareTarget[] {
  const u = encodeURIComponent(url);
  const t = encodeURIComponent(title);
  return [
    { key: "facebook", label: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${u}` },
    {
      key: "linkedin",
      label: "LinkedIn",
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${u}`,
    },
    { key: "x", label: "X", href: `https://twitter.com/intent/tweet?url=${u}&text=${t}` },
    { key: "whatsapp", label: "WhatsApp", href: `https://wa.me/?text=${t}%20${u}` },
    { key: "telegram", label: "Telegram", href: `https://t.me/share/url?url=${u}&text=${t}` },
    { key: "reddit", label: "Reddit", href: `https://www.reddit.com/submit?url=${u}&title=${t}` },
    { key: "mastodon", label: "Mastodon", href: `https://mastodon.social/share?text=${t}%20${u}` },
    { key: "email", label: "Email", href: `mailto:?subject=${t}&body=${u}` },
  ];
}

export function ShareBar({
  url,
  title,
  className = "",
}: {
  url: string;
  title: string;
  className?: string;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const targets = shareTargets(url, title);

  const copy = async () => {
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        /* el usuario canceló: se intenta copiar */
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt(t("friends.copyLink"), url);
    }
  };

  return (
    <div className={`flex flex-wrap items-center gap-1.5 text-xs ${className}`}>
      <span className="text-osap-muted">{t("friends.share")}:</span>
      {targets.map((target) => (
        <a
          key={target.key}
          href={target.href}
          target="_blank"
          rel="noopener nofollow"
          className="rounded border border-osap-border px-2 py-0.5 hover:border-osap-accent hover:text-osap-accent"
        >
          {target.label}
        </a>
      ))}
      <button
        type="button"
        onClick={() => void copy()}
        className="rounded border border-osap-border px-2 py-0.5 hover:border-osap-accent hover:text-osap-accent"
      >
        {copied ? t("friends.copied") : t("friends.copyLink")}
      </button>
    </div>
  );
}
