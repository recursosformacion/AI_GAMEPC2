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
    # Hay página SSR del compositor (algunos anónimos no la tienen: enlazar daría 404).
    composer_page: bool = True


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
    description = (
        f"{title} de {composer_label}"
        + (f" ({catalogue})" if catalogue else "")
        + (f", {year}" if year else "")
        + ". Partituras y recursos disponibles en OpenMusicRepository."
    )

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
        composer_page=composer_page,
    )


def build_representation_payload(
    info: dict[str, object], rep_id: str
) -> dict[str, object] | None:
    """Ficha pública de una representación (indexable y para la app).

    `download_url` solo existe para proveedores servibles (OMR/Mutopia); en el resto se
    ofrece el sitio del proveedor (`site`), nunca el fichero externo (responde 403).
    """
    work_numeric = str(info.get("work_id") or "")
    if not work_numeric.isdigit():
        return None
    work_id = f"index-{int(work_numeric)}"
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

    canonical = canonical_person_url(person_id, slug)
    description = (
        f"Obras y partituras de {name}"
        + (f" ({years})" if years else "")
        + " disponibles en OpenMusicRepository, con recursos musicales y enlaces a cada obra."
    )

    person: dict[str, object] = {
        "@type": "Person",
        "name": name,
        "url": canonical,
        "jobTitle": "Compositor",
    }
    if summary:
        person["description"] = summary
    if nationality:
        person["nationality"] = nationality
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
    )
