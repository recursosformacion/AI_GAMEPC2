// Conversión entre texto plano y HTML sencillo para el cuerpo de los artículos.
//
// La conversión es **no destructiva** para los bloques `<style>…</style>` y para los enlaces:
// se protegen antes de transformar y se restauran al final, de modo que alternar Texto/Código
// nunca pierde el CSS del autor ni sus enlaces.

const STYLE_BLOCK = /<style[\s\S]*?<\/style>/gi;
const PLACEHOLDER = /\u0000B(\d+)\u0000/g;
const MARK = "\u0000";

// Enlaces en texto plano: `[texto](url)` y URLs sueltas (http/https).
const MD_LINK = /\[([^\]\n]{1,200})\]\(([^\s)]{1,500})\)/g;
const BARE_URL = /https?:\/\/[^\s<>"')]+/g;
const ANCHOR = /<a\b[^>]*href\s*=\s*"?([^"\s>]+)"?[^>]*>([\s\S]*?)<\/a>/gi;

function protect(html: string): { text: string; blocks: string[] } {
  const blocks: string[] = [];
  const text = html.replace(STYLE_BLOCK, (match) => {
    blocks.push(match);
    return `${MARK}B${blocks.length - 1}${MARK}`;
  });
  return { text, blocks };
}

function restore(text: string, blocks: string[]): string {
  return text.replace(PLACEHOLDER, (_, index: string) => blocks[Number(index)] ?? "");
}

/** Esquemas admitidos en los enlaces (mismo criterio que el saneado del servidor). */
function safeHref(value: string): string | null {
  const href = value.trim();
  if (href === "") return null;
  const lowered = href.toLowerCase();
  if (
    lowered.startsWith("http://") ||
    lowered.startsWith("https://") ||
    lowered.startsWith("mailto:") ||
    href.startsWith("/") ||
    href.startsWith("#")
  ) {
    return href;
  }
  return null;
}

function autolink(text: string): string {
  return text.replace(BARE_URL, (url) => {
    let clean = url;
    let tail = "";
    while (clean !== "" && ".,;:".includes(clean.charAt(clean.length - 1))) {
      tail = clean.charAt(clean.length - 1) + tail;
      clean = clean.slice(0, -1);
    }
    return clean === ""
      ? tail
      : `<a href="${clean}" rel="nofollow noopener">${clean}</a>${tail}`;
  });
}

function linkify(escaped: string): string {
  const parts: string[] = [];
  let pos = 0;
  for (const match of escaped.matchAll(MD_LINK)) {
    const index = match.index ?? 0;
    parts.push(autolink(escaped.slice(pos, index)));
    const label = (match[1] ?? "").trim();
    const href = safeHref(match[2] ?? "");
    parts.push(
      href !== null && label !== ""
        ? `<a href="${href}" rel="nofollow noopener">${label}</a>`
        : match[0],
    );
    pos = index + match[0].length;
  }
  parts.push(autolink(escaped.slice(pos)));
  return parts.join("");
}

/** Texto plano (párrafos por líneas en blanco) → HTML sencillo seguro con enlaces. */
export function textToHtml(text: string): string {
  const { text: t, blocks } = protect(text);
  const html = t
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p !== "")
    .map((p) => `<p>${linkify(p).replace(/\n/g, "<br>")}</p>`)
    .join("\n");
  return restore(html, blocks);
}

/** HTML sencillo → texto plano (conserva los bloques `<style>` y los enlaces). */
export function htmlToText(html: string): string {
  const { text: t, blocks } = protect(html);
  const plain = t
    .replace(ANCHOR, (_, href: string, label: string) => {
      const text2 = label.replace(/<[^>]+>/g, "").trim();
      return text2 === href ? href : `[${text2}](${href})`;
    })
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*(p|h[1-6]|blockquote|div)\s*>/gi, "\n\n")
    .replace(/<\s*li[^>]*>/gi, "- ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return restore(plain, blocks);
}
