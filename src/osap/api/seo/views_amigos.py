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

from src.osap.api.seo.slug import slugify
from src.osap.api.seo.views import public_base_url
from src.osap.domain.richtext import looks_like_html, plain_text, sanitize_html

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


def _paragraphs(body: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", body or "")
    return [c.strip() for c in chunks if c.strip()]


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
    paragraphs: list[str] = field(default_factory=list)
    cover_url: str | None = None
    media: list[MediaLink] = field(default_factory=list)
    canonical_url: str = ""
    description_meta: str = ""
    og_image: str | None = None
    json_ld: str = ""
    event_date_display: str = ""
    body_html: str | None = None


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
        paragraphs=_paragraphs(body),
        cover_url=cover_url,
        media=media,
        canonical_url=canonical,
        description_meta=description,
        og_image=og_image,
        json_ld=json_ld,
        event_date_display=_euro_date(data.get("event_date")),
        body_html=sanitize_html(body) if looks_like_html(body) else None,
    )
