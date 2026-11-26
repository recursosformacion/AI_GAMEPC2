"""View models de las páginas públicas SEO + construcción de JSON-LD.

Los constructores parten de los diccionarios crudos que devuelve la fachada
(`PlatformApi.seo_*`) y producen objetos tipados que consumen las plantillas. Aquí vive
todo lo derivado de presentación (slug, URL canónica, descripción, datos estructurados)
para que router y plantillas queden triviales.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit

from src.osap.api.seo.slug import person_slug, work_canonical_slug

_DEFAULT_BASE_URL = "https://app.openmusicrepository.com"
_JSON_LD_CONTEXT = "https://schema.org"


def public_base_url() -> str:
    """Base canónica del sitio público (configurable por `OSAP_PUBLIC_BASE_URL`)."""
    return os.environ.get("OSAP_PUBLIC_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _site_of(url: str | None) -> str | None:
    """Sitio del proveedor (`https://host/`) para «abrir en …» sin enlazar el fichero crudo.

    Los ficheros de CPDL/IMSLP responden 403 a peticiones directas, así que cuando no hay
    copia servible se enlaza el sitio del proveedor, no el fichero.
    """
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}/"


def _str_or_none(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _int_or_none(value: object) -> int | None:
    text = str(value).strip() if value is not None else ""
    return int(text) if text.isdigit() else None


def _year_label(birth: object, death: object) -> str | None:
    b = _str_or_none(birth)
    d = _str_or_none(death)
    if b and d:
        return f"{b}–{d}"
    if b:
        return f"{b}–"
    if d:
        return f"–{d}"
    return None


@dataclass(frozen=True)
class WorkLink:
    work_id: str
    slug: str
    title: str
    catalogue: str | None = None


@dataclass(frozen=True)
class RepresentationLink:
    provider: str
    format: str
    url: str | None
    downloadable: bool
    # Sitio del proveedor (para «abrir en …» cuando no hay fichero servible). Enlazar el
    # fichero crudo de CPDL/IMSLP falla (403): solo se enlaza si es descargable.
    site: str | None = None
    # Id determinista (`idx-<work>-<provider>-<resource>-<format>`) → `/representacion/<id>`.
    id: str | None = None


@dataclass(frozen=True)
class WorkView:
    work_id: str
    slug: str
    title: str
    composer: str | None
    composer_id: str | None
    composer_slug: str | None
    catalogue: str | None
    year: int | None
    instrumentation: str | None
    representations: list[RepresentationLink] = field(default_factory=list)
    related: list[WorkLink] = field(default_factory=list)
    canonical_url: str = ""
    description: str = ""
    json_ld: str = ""
    # Contenido y metadatos ampliados de la obra (procedentes de storage).
    description_text: str = ""
    genres: list[str] = field(default_factory=list)
    opus: str | None = None
    musical_key: str | None = None
    source_url: str | None = None
    license: str | None = None
    public_domain: bool = False
    attribution_type: str | None = None
    duration: str | None = None
    language: str | None = None
    epoch: str | None = None
    source_links: list[AuthorityLink] = field(default_factory=list)
    # Hay página SSR del compositor (algunos anónimos no la tienen: enlazar daría 404).
    composer_page: bool = True


@dataclass(frozen=True)
class AuthorityLink:
    """Enlace a una fuente de autoridad o referencia externa."""

    label: str
    url: str


@dataclass(frozen=True)
class PersonView:
    person_id: str
    slug: str
    name: str
    years: str | None
    era: str | None
    nationality: str | None
    summary: str | None
    key_works: list[str] = field(default_factory=list)
    works: list[WorkLink] = field(default_factory=list)
    works_total: int = 0
    canonical_url: str = ""
    description: str = ""
    json_ld: str = ""
    # Texto único de la ficha: biografía si existe; si no, ficha catalográfica factual.
    intro: str = ""
    catalog_note: str = ""
    authority_links: list[AuthorityLink] = field(default_factory=list)
    reference_links: list[AuthorityLink] = field(default_factory=list)
    has_biography: bool = False
    # Campos del formulario de persona (vista de solo lectura en la ficha pública).
    givenname: str | None = None
    familyname: str | None = None
    sortname: str | None = None
    display_nationality: str | None = None
    biography_nationality: str | None = None
    birth_year: str | None = None
    death_year: str | None = None
    image_url: str | None = None
    biography_key_fact: str | None = None
    biography_references: str | None = None
    visible: bool = False


def canonical_work_url(work_id: str, slug: str) -> str:
    return f"{public_base_url()}/obras/{work_id}/{slug}"


def canonical_person_url(person_id: str, slug: str) -> str:
    return f"{public_base_url()}/composers/{person_id}/{slug}"


def _breadcrumb_json_ld(items: list[tuple[str, str | None]]) -> dict[str, object]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": name,
                **({"item": url} if url else {}),
            }
            for index, (name, url) in enumerate(items)
        ],
    }


def _dump(payload: dict[str, object]) -> str:
    """Serializa JSON-LD seguro para insertar dentro de `<script>`.

    `json.dumps` NO escapa `<`, `>` ni `&`; un título/compositor con `</script>` podría
    cerrar el bloque e inyectar HTML. Se escapan como secuencias `\\uXXXX` (JSON válido).
    """
    text = json.dumps(payload, ensure_ascii=False)
    return (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build_work_view(
    data: dict[str, object],
    related: list[dict[str, object]],
    *,
    composer_page: bool = True,
) -> WorkView:
    work_id = str(data.get("work_id") or "")
    title = str(data.get("title") or "").strip() or "Obra"
    composer = _str_or_none(data.get("composer"))
    slug = work_canonical_slug(title)
    composer_id = _str_or_none(data.get("composer_id"))
    catalogue = _str_or_none(data.get("catalogue"))
    year = _int_or_none(data.get("year"))
    instrumentation = _str_or_none(data.get("instrumentation"))
    composer_slug = person_slug(composer) if composer else None
    opus = _str_or_none(data.get("opus"))
    musical_key = _str_or_none(data.get("musical_key"))
    source_url = _str_or_none(data.get("source_url"))
    license_name = _str_or_none(data.get("license"))
    public_domain = bool(data.get("public_domain"))
    attribution_type = _str_or_none(data.get("attribution_type"))
    duration = _str_or_none(data.get("duration"))
    language = _str_or_none(data.get("language"))
    epoch = _str_or_none(data.get("epoch") or data.get("epoch_title"))
    raw_genres = data.get("genres")
    genres = [
        str(item).strip()
        for item in (raw_genres if isinstance(raw_genres, list) else [])
        if str(item).strip()
    ]
    description_text = _str_or_none(data.get("description")) or ""

    raw_reps = data.get("representations")
    representations: list[RepresentationLink] = []
    if isinstance(raw_reps, list):
        for rep in raw_reps:
            if not isinstance(rep, dict):
                continue
            url = _str_or_none(rep.get("url"))
            representations.append(
                RepresentationLink(
                    provider=str(rep.get("provider") or ""),
                    format=str(rep.get("format") or "").upper(),
                    url=url,
                    downloadable=bool(rep.get("downloadable")) and url is not None,
                    site=_site_of(url),
                    id=_str_or_none(rep.get("id")),
                )
            )

    related_links: list[WorkLink] = []
    for item in related:
        item_title = str(item.get("title") or "")
        if not item_title:
            continue
        related_links.append(
            WorkLink(
                work_id=str(item.get("work_id") or ""),
                slug=work_canonical_slug(item_title),
                title=item_title,
                catalogue=_str_or_none(item.get("catalogue")),
            )
        )

    canonical = canonical_work_url(work_id, slug)
    composer_label = composer or "compositor desconocido"
    if not description_text:
        parts = [f"«{title}» es una obra de {composer_label}"]
        if year:
            parts.append(f"compuesta en {year}")
        if instrumentation:
            parts.append(f"para {instrumentation}")
        if genres:
            parts.append(f"del género {genres[0]}")
        description_text = ", ".join(parts) + "."
    description = _clip(
        f"{title} de {composer_label}"
        + (f" ({catalogue})" if catalogue else "")
        + (f", {year}" if year else "")
        + f". {description_text}"
    )
    source_links: list[AuthorityLink] = []
    if source_url and source_url.startswith("http"):
        host = urlsplit(source_url).netloc.lower()
        label = "IMSLP" if "imslp.org" in host else "CPDL" if "cpdl.org" in host else host
        source_links.append(AuthorityLink(label=label, url=source_url))

    breadcrumb: list[tuple[str, str | None]] = [("Inicio", public_base_url() + "/")]
    if composer and composer_id and composer_slug and composer_page:
        breadcrumb.append(("Compositores", public_base_url() + "/composers"))
        breadcrumb.append((composer, canonical_person_url(composer_id, composer_slug)))
    breadcrumb.append((title, None))

    composition: dict[str, object] = {
        "@type": "MusicComposition",
        "name": title,
        "url": canonical,
        "identifier": catalogue or work_id,
    }
    if composer:
        composer_node: dict[str, object] = {"@type": "Person", "name": composer}
        if composer_id and composer_slug and composer_page:
            composer_node["url"] = canonical_person_url(composer_id, composer_slug)
        composition["composer"] = composer_node
    if year:
        composition["datePublished"] = str(year)
    composition["description"] = description_text
    if genres:
        composition["genre"] = genres
    if musical_key:
        composition["musicalKey"] = musical_key
    if language:
        composition["inLanguage"] = language
    if source_url and source_url.startswith("http"):
        composition["sameAs"] = source_url
    if license_name and license_name.startswith("http"):
        composition["license"] = license_name

    json_ld = _dump(
        {
            "@context": _JSON_LD_CONTEXT,
            "@graph": [composition, _breadcrumb_json_ld(breadcrumb)],
        }
    )

    return WorkView(
        work_id=work_id,
        slug=slug,
        title=title,
        composer=composer,
        composer_id=composer_id,
        composer_slug=composer_slug,
        catalogue=catalogue,
        year=year,
        instrumentation=instrumentation,
        representations=representations,
        related=related_links,
        canonical_url=canonical,
        description=description,
        json_ld=json_ld,
        description_text=description_text,
        genres=genres,
        opus=opus,
        musical_key=musical_key,
        source_url=source_url,
        license=license_name,
        public_domain=public_domain,
        attribution_type=attribution_type,
        duration=duration,
        language=language,
        epoch=epoch,
        source_links=source_links,
        composer_page=composer_page,
    )


def build_representation_payload(
    info: dict[str, object], rep_id: str
) -> dict[str, object] | None:
    """Ficha pública de una representación (indexable y para la app).

    `download_url` solo existe para proveedores servibles (OMR/Mutopia); en el resto se
    ofrece el sitio del proveedor (`site`), nunca el fichero externo (responde 403).
    """
    work_ref = str(info.get("work_id") or "").strip()
    if not work_ref:
        return None
    work_id = work_ref if work_ref.startswith("index-") else f"index-{work_ref}"
    title = str(info.get("title") or "").strip() or "Obra"
    composer = _str_or_none(info.get("composer"))
    catalogue = _str_or_none(info.get("catalogue"))
    provider = str(info.get("provider") or "")
    fmt = str(info.get("format") or "").upper()
    download_url = _str_or_none(info.get("download_url"))
    view_url = _str_or_none(info.get("view_url"))
    site = _site_of(view_url)
    work_slug = work_canonical_slug(title)
    canonical = f"{public_base_url()}/representacion/{quote(rep_id, safe='')}"
    composer_label = composer or "compositor desconocido"
    description = (
        f"{fmt or 'Recurso'} de «{title}» de {composer_label} en {provider}. "
        "Ficha, visor y descarga en OpenMusicRepository."
    )
    json_ld: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "MediaObject",
        "name": f"{title} — {provider} {fmt}".strip(),
        "encodingFormat": fmt.lower(),
        "url": canonical,
        "description": description,
        "isPartOf": {
            "@type": "MusicComposition",
            "name": title,
            "url": canonical_work_url(work_id, work_slug),
        },
    }
    if download_url:
        json_ld["contentUrl"] = download_url
    return {
        "id": rep_id,
        "provider": provider,
        "format": fmt,
        "title": title,
        "composer": composer,
        "catalogue": catalogue,
        "work_id": work_id,
        "work_path": f"/obras/{work_id}/{work_slug}",
        "download_url": download_url,
        "site": site,
        "canonical_url": canonical,
        "description": description,
        "json_ld": json.dumps(json_ld, ensure_ascii=False),
    }


_AUTHORITY_URLS: dict[str, tuple[str, str]] = {
    "wikidata_qid": ("Wikidata", "https://www.wikidata.org/wiki/{value}"),
    "viaf": ("VIAF", "https://viaf.org/viaf/{value}"),
    "imslp": ("IMSLP", "https://imslp.org/wiki/{value}"),
    "musicbrainz": ("MusicBrainz", "https://musicbrainz.org/artist/{value}"),
    "mbid": ("MusicBrainz", "https://musicbrainz.org/artist/{value}"),
    "gnd": ("GND", "https://d-nb.info/gnd/{value}"),
    "isni": ("ISNI", "https://isni.org/isni/{value}"),
    "rism": ("RISM", "https://rism.online/{value}"),
    "bnf": ("BnF", "https://data.bnf.fr/ark:/12148/{value}"),
    "lccn": ("LCCN", "https://id.loc.gov/authorities/names/{value}.html"),
    "discogs": ("Discogs", "https://www.discogs.com/artist/{value}"),
}


def _authority_links(raw: object) -> list[AuthorityLink]:
    if not isinstance(raw, list):
        return []
    links: list[AuthorityLink] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("id_type") or item.get("identity_type") or "").lower()
        value = str(item.get("id_value") or item.get("identity_value") or "").strip()
        spec = _AUTHORITY_URLS.get(kind)
        if not value or spec is None:
            continue
        label, template = spec
        url = template.format(value=quote(value, safe="/'(),:_-"))
        if url in seen:
            continue
        seen.add(url)
        links.append(AuthorityLink(label=label, url=url))
    return links


def _reference_links(raw: object) -> list[AuthorityLink]:
    if isinstance(raw, str):
        items: list[object] = [part.strip() for part in raw.split(";") if part.strip()]
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    links: list[AuthorityLink] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("source") or item.get("title") or item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
        else:
            label = str(item).strip()
            url = ""
        if not label and not url:
            continue
        key = url or label.lower()
        if key in seen:
            continue
        seen.add(key)
        links.append(AuthorityLink(label=label or url, url=url))
    return links


def _image_url(raw: object) -> str | None:
    image = _str_or_none(raw)
    if not image:
        return None
    if image.startswith("//"):
        return "https:" + image
    if image.startswith("http://"):
        host = urlsplit(image).netloc.lower()
        if host in {"commons.wikimedia.org", "upload.wikimedia.org"}:
            return "https://" + image[len("http://"):]
        return image
    if image.startswith("https://"):
        return image
    if image.startswith("/"):
        return public_base_url() + image
    # Wikidata P18 suele venir como nombre de fichero de Commons.
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(
        image, safe="%/:"
    )


def _clip(text: str, limit: int = 158) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return cut + "…"


def _catalog_intro(
    name: str,
    years: str | None,
    nationality: str | None,
    era: str | None,
    total: int,
    titles: list[str],
) -> str:
    lead = f"{name}{f' ({years})' if years else ''}"
    works_word = f"obra{'s' if total != 1 else ''}"
    documented = f"documentada{'s' if total != 1 else ''}"
    parts = [f"{lead} reúne {total} {works_word} {documented} en OpenMusicRepository"]
    if nationality:
        parts.append(f"con nacionalidad {nationality}")
    if era:
        parts.append(f"adscrito a la época {era}")
    text = ", ".join(parts) + "."
    if titles:
        quoted = ", ".join(f"«{title}»" for title in titles[:4])
        text += f" Entre las obras catalogadas figuran {quoted}."
    return text


def build_person_view(detail: dict[str, object], works: dict[str, object]) -> PersonView:
    person_id = str(detail.get("id") or "")
    name = str(detail.get("name") or "").strip() or "Compositor"
    slug = person_slug(name)
    years = _year_label(detail.get("birth_year"), detail.get("death_year"))
    era = _str_or_none(detail.get("biography_era"))
    nationality = _str_or_none(detail.get("biography_nationality"))
    summary = _str_or_none(detail.get("biography_summary"))
    key_works_raw = detail.get("biography_key_works")
    key_works = (
        [str(k) for k in key_works_raw if isinstance(k, str)]
        if isinstance(key_works_raw, list)
        else []
    )

    raw_items = works.get("items")
    work_links: list[WorkLink] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_title = str(item.get("title") or "")
            if not item_title:
                continue
            work_links.append(
                WorkLink(
                    work_id=str(item.get("work_id") or ""),
                    slug=work_canonical_slug(item_title),
                    title=item_title,
                    catalogue=_str_or_none(item.get("catalogue")),
                )
            )
    total = _int_or_none(works.get("total")) or len(work_links)
    authority_links = _authority_links(detail.get("identifiers"))
    reference_links = _reference_links(detail.get("biography_references"))
    display_nationality = _str_or_none(detail.get("nationality")) or nationality
    image_url = _image_url(detail.get("image_url"))
    has_biography = bool(summary)
    work_titles = [link.title for link in work_links]
    intro = summary or _catalog_intro(
        name, years, display_nationality, era, total, work_titles
    )
    catalog_note = (
        f"Ficha catalográfica de {name}: {total} obra{'s' if total != 1 else ''} "
        f"documentada{'s' if total != 1 else ''} en OpenMusicRepository"
        + (
            f", con {len(authority_links)} enlace{'s' if len(authority_links) != 1 else ''} "
            "a fuentes de autoridad."
            if authority_links
            else "."
        )
    )

    canonical = canonical_person_url(person_id, slug)
    base_description = (
        f"{name}{f' ({years})' if years else ''}: {total} obra{'s' if total != 1 else ''} "
        "y partituras en OpenMusicRepository"
    )
    description = _clip(
        base_description + (f". {summary}" if summary else f". {intro}")
    )

    person: dict[str, object] = {
        "@type": "Person",
        "name": name,
        "url": canonical,
        "jobTitle": "Compositor",
    }
    person["description"] = summary or intro
    if display_nationality:
        person["nationality"] = display_nationality
    if image_url:
        person["image"] = image_url
    if authority_links:
        person["sameAs"] = [link.url for link in authority_links]
    birth = _str_or_none(detail.get("birth_year"))
    death = _str_or_none(detail.get("death_year"))
    if birth and len(birth) == 4 and birth.isdigit():
        person["birthDate"] = birth
    if death and len(death) == 4 and death.isdigit():
        person["deathDate"] = death

    json_ld = _dump(
        {
            "@context": _JSON_LD_CONTEXT,
            "@graph": [
                person,
                _breadcrumb_json_ld(
                    [
                        ("Inicio", public_base_url() + "/"),
                        ("Compositores", public_base_url() + "/composers"),
                        (name, None),
                    ]
                ),
            ],
        }
    )

    return PersonView(
        person_id=person_id,
        slug=slug,
        name=name,
        years=years,
        era=era,
        nationality=nationality,
        summary=summary,
        key_works=key_works,
        works=work_links,
        works_total=total,
        canonical_url=canonical,
        description=description,
        json_ld=json_ld,
        intro=intro,
        catalog_note=catalog_note,
        authority_links=authority_links,
        reference_links=reference_links,
        has_biography=has_biography,
        givenname=_str_or_none(detail.get("given_name") or detail.get("givenname")),
        familyname=_str_or_none(detail.get("family_name") or detail.get("familyname")),
        sortname=_str_or_none(detail.get("sort_name") or detail.get("sortname")),
        display_nationality=display_nationality,
        biography_nationality=nationality,
        birth_year=_str_or_none(detail.get("birth_year")),
        death_year=_str_or_none(detail.get("death_year")),
        image_url=image_url,
        biography_key_fact=_str_or_none(detail.get("biography_key_fact")),
        biography_references=None,
        visible=bool(detail.get("visible", True)),
    )
