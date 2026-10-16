"""View models de las páginas públicas de «Los amigos» (grupo y artículo).

Reutilizan el patrón de `seo/views.py`: a partir de los diccionarios crudos de la fachada
se produce un objeto tipado para las plantillas Jinja, con URL canónica, descripción y
JSON-LD. El cuerpo del artículo se trata como TEXTO (nunca HTML): se parte en párrafos para
evitar inyección de marcado por parte de los autores.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from src.osap.api.seo.slug import slugify
from src.osap.api.seo.views import public_base_url
from src.osap.domain.richtext import plain_text, to_html_body

_IMG_EXT = re.compile(r"\.(jpg|jpeg|png|webp|gif|avif)(\?|$)", re.IGNORECASE)


def group_canonical_url(group_id: str, slug: str) -> str:
    return f"{public_base_url()}/amigos/corales/{group_id}/{slug}"


def article_canonical_url(article_id: str, slug: str) -> str:
    return f"{public_base_url()}/amigos/articulo/{article_id}/{slug}"


def _str_or_none(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _euro_date(value: object) -> str:
    """Fecha ISO (`AAAA-MM-DD`) → formato europeo `dd/mm/aaaa` para mostrar."""
    text = str(value).strip() if value is not None else ""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    return f"{match.group(3)}/{match.group(2)}/{match.group(1)}" if match else text


def _build_coral_view(raw: object) -> CoralView | None:
    if not isinstance(raw, dict):
        return None

    def opt(key: str) -> str | None:
        value = raw.get(key)
        text = str(value).strip() if value is not None else ""
        return text or None

    count = raw.get("member_count")
    repertoire = raw.get("repertoire")
    languages = raw.get("languages")
    places = raw.get("places")
    return CoralView(
        foundation_date=_euro_date(opt("foundation_date")),
        dissolution_date=_euro_date(opt("dissolution_date")),
        locality=opt("locality"),
        region=opt("region"),
        country_code=opt("country_code"),
        venue=opt("venue"),
        formation_type=opt("formation_type"),
        member_count=int(str(count)) if count not in (None, "") else None,
        website=opt("website"),
        public_email=opt("public_email"),
        director_label=opt("director_label"),
        linked_entity=opt("linked_entity"),
        repertoire=[str(v) for v in repertoire] if isinstance(repertoire, list) else [],
        languages=[str(v) for v in languages] if isinstance(languages, list) else [],
        places=[str(v) for v in places] if isinstance(places, list) else [],
    )


def _youtube_embed(video_id: str | None) -> str | None:
    return f"https://www.youtube.com/embed/{video_id}" if video_id else None


def _dump(payload: dict[str, object]) -> str:
    text = json.dumps(payload, ensure_ascii=False)
    return (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


@dataclass(frozen=True)
class MediaLink:
    kind: str
    url: str
    embed_url: str | None = None
    caption: str | None = None
    credit: str | None = None


@dataclass(frozen=True)
class ArticleLink:
    article_id: str
    slug: str
    title: str
    event_date: str
    summary: str | None = None
    event_date_display: str = ""


@dataclass(frozen=True)
class GroupLink:
    kind: str
    url: str
    label: str | None = None


@dataclass(frozen=True)
class CoralView:
    foundation_date: str | None = None
    dissolution_date: str | None = None
    locality: str | None = None
    region: str | None = None
    country_code: str | None = None
    venue: str | None = None
    formation_type: str | None = None
    member_count: int | None = None
    website: str | None = None
    public_email: str | None = None
    director_label: str | None = None
    linked_entity: str | None = None
    repertoire: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return any(
            [
                self.foundation_date, self.dissolution_date, self.locality, self.region,
                self.country_code, self.venue, self.formation_type, self.member_count,
                self.website, self.public_email, self.director_label, self.linked_entity,
                self.repertoire, self.languages, self.places,
            ]
        )


@dataclass(frozen=True)
class ShareTarget:
    """Destino de compartición: enlace con intención web + icono SVG en línea."""

    key: str
    label: str
    href: str
    icon: str


# Iconos de marca en SVG en línea (rutas de Simple Icons, CC0). El nombre del destino va en
# `title`/`aria-label`, no como texto, para que la barra sea compacta.
_SHARE_ICON = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">{}</svg>'
)
_SHARE_ICONS: dict[str, str] = {
    "facebook": (
        '<path d="M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 '
        ".955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 "
        "26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374"
        ".995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 "
        '12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z"/>'
    ),
    "linkedin": (
        '<path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136'
        " 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 "
        "5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 "
        "2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225"
        " 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 "
        '22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>'
    ),
    "x": (
        '<path d="M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33'
        "l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 "
        '7.754 11.09h-3.182z"/>'
    ),
    "whatsapp": (
        '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297'
        "-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48"
        "-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298"
        ".298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669"
        "-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 "
        "1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712"
        ".227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074"
        "-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982"
        ".998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 "
        "5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413"
        "-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945"
        'L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a'
        '11.821 11.821 0 00-3.48-8.413Z"/>'
    ),
    "telegram": (
        '<path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 '
        "12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306"
        ".02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9"
        "-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 "
        "3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345"
        "-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027"
        "-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476"
        '-1.635z"/>'
    ),
    "reddit": (
        '<path d="M12 0C5.373 0 0 5.373 0 12c0 3.314 1.343 6.314 3.515 8.485l-2.286 2.286C.775 23.225'
        " 1.097 24 1.738 24H12c6.627 0 12-5.373 12-12S18.627 0 12 0Zm4.388 3.199c1.104 0 1.999.895 "
        "1.999 1.999 0 1.105-.895 2-1.999 2-.946 0-1.739-.657-1.947-1.539v.002c-1.147.162-2.032 1.15"
        "-2.032 2.341v.007c1.776.067 3.4.567 4.686 1.363.473-.363 1.064-.58 1.707-.58 1.547 0 2.802 "
        "1.254 2.802 2.802 0 1.117-.655 2.081-1.601 2.531-.088 3.256-3.637 5.876-7.997 5.876-4.361 "
        "0-7.905-2.617-7.998-5.87-.954-.447-1.614-1.415-1.614-2.538 0-1.548 1.255-2.802 2.803-2.802"
        ".645 0 1.239.218 1.712.585 1.275-.79 2.881-1.291 4.64-1.365v-.01c0-1.663 1.263-3.034 "
        "2.88-3.207.188-.911.993-1.595 1.959-1.595Zm-8.085 8.376c-.784 0-1.459.78-1.506 1.797-.047 "
        "1.016.64 1.429 1.426 1.429.786 0 1.371-.369 1.418-1.385.047-1.017-.553-1.841-1.338-1.841Z"
        "m7.406 0c-.786 0-1.385.824-1.338 1.841.047 1.017.634 1.385 1.418 1.385.785 0 1.473-.413 "
        "1.426-1.429-.046-1.017-.721-1.797-1.506-1.797Zm-3.703 4.013c-.974 0-1.907.048-2.77.135"
        "-.147.015-.241.168-.183.305.483 1.154 1.622 1.964 2.953 1.964 1.33 0 2.47-.81 2.953-1.964"
        '.057-.137-.037-.29-.184-.305-.863-.087-1.795-.135-2.769-.135Z"/>'
    ),
    "mastodon": (
        '<path d="M23.268 5.313c-.35-2.578-2.617-4.61-5.304-5.004C17.51.242 15.792 0 11.813 0h-.03c'
        "-3.98 0-4.835.242-5.288.309C3.882.692 1.496 2.518.917 5.127.64 6.412.61 7.837.661 9.143c"
        ".074 1.874.088 3.745.26 5.611.118 1.24.325 2.47.62 3.68.55 2.237 2.777 4.098 4.96 4.857 "
        "2.336.792 4.849.923 7.256.38.265-.061.527-.132.786-.213.585-.184 1.27-.39 1.774-.753a.057"
        ".057 0 0 0 .023-.043v-1.809a.052.052 0 0 0-.02-.041.053.053 0 0 0-.046-.01 20.282 20.282 "
        "0 0 1-4.709.545c-2.73 0-3.463-1.284-3.674-1.818a5.593 5.593 0 0 1-.319-1.433.053.053 0 0 "
        "1 .066-.054c1.517.363 3.072.546 4.632.546.376 0 .75 0 1.125-.01 1.57-.044 3.224-.124 "
        "4.768-.422.038-.008.077-.015.11-.024 2.435-.464 4.753-1.92 4.989-5.604.008-.145.03-1.52"
        ".03-1.67.002-.512.167-3.63-.024-5.545zm-3.748 9.195h-2.561V8.29c0-1.309-.55-1.976-1.67"
        "-1.976-1.23 0-1.846.79-1.846 2.35v3.403h-2.546V8.663c0-1.56-.617-2.35-1.848-2.35-1.112 "
        "0-1.668.668-1.67 1.977v6.218H4.822V8.102c0-1.31.337-2.35 1.011-3.12.696-.77 1.608-1.164 "
        "2.74-1.164 1.311 0 2.302.5 2.962 1.498l.638 1.06.638-1.06c.66-.999 1.65-1.498 2.96-1.498 "
        "1.13 0 2.043.395 2.74 1.164.675.77 1.012 1.81 1.012 3.12z\"/>"
    ),
    # El correo no tiene marca: sobre dibujado a trazo (mismo estilo que los iconos de la app).
    "email": (
        '<g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/>'
        '<path d="m3 7 9 6 9-6"/></g>'
    ),
}


def share_targets(url: str, title: str) -> list[ShareTarget]:
    """Enlaces de «compartir» para una URL pública, con su icono.

    Cubre las redes con intención web. **Instagram no ofrece una**: para él se usa
    «Copiar enlace» o la hoja nativa del sistema (`navigator.share`), que incluye Instagram
    en móvil/escritorio.
    """
    u = quote(url, safe="")
    t = quote(title, safe="")
    entries = [
        ("facebook", "Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
        ("linkedin", "LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={u}"),
        ("x", "X", f"https://twitter.com/intent/tweet?url={u}&text={t}"),
        ("whatsapp", "WhatsApp", f"https://wa.me/?text={t}%20{u}"),
        ("telegram", "Telegram", f"https://t.me/share/url?url={u}&text={t}"),
        ("reddit", "Reddit", f"https://www.reddit.com/submit?url={u}&title={t}"),
        ("mastodon", "Mastodon", f"https://mastodon.social/share?text={t}%20{u}"),
        ("email", "Email", f"mailto:?subject={t}&body={u}"),
    ]
    return [
        ShareTarget(key=key, label=label, href=href, icon=_SHARE_ICON.format(_SHARE_ICONS[key]))
        for key, label, href in entries
    ]



@dataclass(frozen=True)
class GroupView:
    group_id: str
    slug: str
    name: str
    kind: str
    description: str | None
    image_url: str | None
    website: str | None = None
    email: str | None = None
    logo_url: str | None = None
    links: list[GroupLink] = field(default_factory=list)
    articles: list[ArticleLink] = field(default_factory=list)
    coral: CoralView | None = None
    canonical_url: str = ""
    description_meta: str = ""
    json_ld: str = ""
    share: list[ShareTarget] = field(default_factory=list)


@dataclass(frozen=True)
class ArticleView:
    article_id: str
    slug: str
    title: str
    event_date: str
    published_at: str | None
    group_id: str
    group_slug: str
    group_name: str
    group_url: str
    summary: str | None
    cover_url: str | None = None
    media: list[MediaLink] = field(default_factory=list)
    canonical_url: str = ""
    description_meta: str = ""
    og_image: str | None = None
    json_ld: str = ""
    event_date_display: str = ""
    body_html: str | None = None
    share: list[ShareTarget] = field(default_factory=list)


def _breadcrumb(items: list[tuple[str, str | None]]) -> dict[str, object]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, **({"item": url} if url else {})}
            for i, (name, url) in enumerate(items)
        ],
    }


def build_group_view(data: dict[str, object]) -> GroupView:
    group_id = str(data.get("id") or "")
    name = str(data.get("name") or "").strip() or "Grupo"
    slug = slugify(str(data.get("slug") or name)) or "grupo"
    description = _str_or_none(data.get("description"))
    raw_articles = data.get("articles")
    articles: list[ArticleLink] = []
    if isinstance(raw_articles, list):
        for item in raw_articles:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            if not title:
                continue
            articles.append(
                ArticleLink(
                    article_id=str(item.get("id") or ""),
                    slug=slugify(title) or "articulo",
                    title=title,
                    event_date=str(item.get("event_date") or ""),
                    summary=_str_or_none(item.get("summary")),
                    event_date_display=_euro_date(item.get("event_date")),
                )
            )
    canonical = group_canonical_url(group_id, slug)
    description_meta = description or f"Publicaciones y actividades de {name} en OpenMusicRepository."
    coral = _build_coral_view(data.get("coral"))
    json_ld = _dump(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "name": name,
                    "url": canonical,
                    "description": description_meta,
                },
                _breadcrumb(
                    [
                        ("Inicio", public_base_url() + "/"),
                        ("Los amigos", public_base_url() + "/amigos"),
                        (name, None),
                    ]
                ),
            ],
        }
    )
    links: list[GroupLink] = []
    raw_links = data.get("links")
    if isinstance(raw_links, list):
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            url = _str_or_none(item.get("url"))
            if not url:
                continue
            links.append(
                GroupLink(
                    kind=str(item.get("kind") or ""),
                    url=url,
                    label=_str_or_none(item.get("label")),
                )
            )
    return GroupView(
        group_id=group_id,
        slug=slug,
        name=name,
        kind=str(data.get("kind") or "coral"),
        description=description,
        image_url=_str_or_none(data.get("image_url")),
        website=_str_or_none(data.get("website")),
        email=_str_or_none(data.get("email")),
        logo_url=_str_or_none(data.get("logo_url")),
        links=links,
        articles=articles,
        coral=coral,
        canonical_url=canonical,
        description_meta=description_meta,
        json_ld=json_ld,
        share=share_targets(canonical, name),
    )


def build_article_view(data: dict[str, object]) -> ArticleView:
    article_id = str(data.get("id") or "")
    title = str(data.get("title") or "").strip() or "Artículo"
    slug = slugify(title) or "articulo"
    event_date = str(data.get("event_date") or "")
    group_id = str(data.get("group_id") or "")
    is_general = group_id == ""
    group_slug = str(data.get("group_slug") or "") or "grupo"
    group_name = "Artículos" if is_general else str(data.get("group_name") or "Grupo")
    summary = _str_or_none(data.get("summary"))
    body = str(data.get("body") or "")
    cover_url = _str_or_none(data.get("cover_url"))
    media: list[MediaLink] = []
    raw_media = data.get("media")
    if isinstance(raw_media, list):
        for item in raw_media:
            if not isinstance(item, dict):
                continue
            url = _str_or_none(item.get("url"))
            if not url:
                continue
            media.append(
                MediaLink(
                    kind=str(item.get("kind") or ""),
                    url=url,
                    embed_url=_youtube_embed(_str_or_none(item.get("video_id"))),
                    caption=_str_or_none(item.get("caption")),
                    credit=_str_or_none(item.get("credit")),
                )
            )
    group_url = (
        f"{public_base_url()}/amigos/articulos"
        if is_general
        else group_canonical_url(group_id, group_slug)
    )
    canonical = article_canonical_url(article_id, slug)
    body_text = plain_text(body)
    description = summary or (
        body_text[:180].strip() + ("…" if len(body_text) > 180 else "")
    )
    if not description:
        description = f"{title} — {group_name}"
    og_image = cover_url
    if og_image is None:
        for item in media:
            if item.kind == "photo" and _IMG_EXT.search(item.url):
                og_image = item.url
                break
    image_node: dict[str, object] = {}
    if og_image:
        image_node = {"@type": "ImageObject", "url": og_image}
    json_ld = _dump(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Article",
                    "headline": title,
                    "url": canonical,
                    "datePublished": event_date,
                    **({"articleBody": summary} if summary else {}),
                    **({"image": image_node} if image_node else {}),
                    "publisher": {
                        "@type": "Organization",
                        "name": group_name,
                        "url": group_url,
                    },
                },
                _breadcrumb(
                    [
                        ("Inicio", public_base_url() + "/"),
                        ("Los amigos", public_base_url() + "/amigos"),
                        (group_name, group_url),
                        (title, None),
                    ]
                ),
            ],
        }
    )
    return ArticleView(
        article_id=article_id,
        slug=slug,
        title=title,
        event_date=event_date,
        published_at=_str_or_none(data.get("published_at")),
        group_id=group_id,
        group_slug=group_slug,
        group_name=group_name,
        group_url=group_url,
        summary=summary,
        cover_url=cover_url,
        media=media,
        canonical_url=canonical,
        description_meta=description,
        og_image=og_image,
        json_ld=json_ld,
        event_date_display=_euro_date(data.get("event_date")),
        body_html=to_html_body(body) or None,
        share=share_targets(canonical, title),
    )
