// Conversión entre texto plano y HTML sencillo para el cuerpo de los artículos.
//
// La conversión es **no destructiva** para los bloques `<style>…</style>`: se protegen antes
// de transformar y se restauran al final, de modo que alternar Texto/Código nunca pierde el
// CSS del autor.

const STYLE_BLOCK = /<style[\s\S]*?<\/style>/gi;
const PLACEHOLDER = /\u0000B(\d+)\u0000/g;
const MARK = "\u0000";

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

/** Texto plano (párrafos por líneas en blanco) → HTML sencillo seguro. */
export function textToHtml(text: string): string {
  const { text: t, blocks } = protect(text);
  const html = t
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p !== "")
    .map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`)
    .join("\n");
  return restore(html, blocks);
}

/** HTML sencillo → texto plano (conserva los bloques `<style>`). */
export function htmlToText(html: string): string {
  const { text: t, blocks } = protect(html);
  const plain = t
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
