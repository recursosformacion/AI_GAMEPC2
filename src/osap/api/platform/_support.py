"""Helpers y clases de soporte del Platform API (F5.4)."""

import ipaddress
import logging
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from src.osap.api.contracts import (
    ProviderResponse,
    RepositorySource,
    RepositorySourceSummary,
    SearchRequest,
    SessionSource,
    SourceObservation,
)
from src.osap.application.canonicalizer import Canonicalizer
from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.representation_selector import (
    SelectedRepresentation,
)
from src.osap.domain.knowledge import KnowledgeBase
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import ProviderId
from src.osap.infrastructure.http.browser_headers import browser_headers

VERSION = "3.1"


def _validate_preview_url(url: str) -> str | None:
    """Valida que una URL de preview sea http(s) y no apunte a rangos privados/locales.

    Mitigación de SSRF (ADR-0036): los hosts por IP se rechazan si son privados,
    loopback, link-local, reservados o multicast; los hostnames solo se rechazan si
    son localhost, intranet sin punto o TLD internos (.local/.internal/.localhost).
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return "Invalid URL"
    if parsed.scheme not in ("http", "https"):
        return "Only http/https URLs are supported"
    host = parsed.hostname
    if not host:
        return "URL without host"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return "Private/local addresses are not allowed"
        return None
    low = host.lower()
    if low == "localhost" or "." not in low or low.endswith((".local", ".internal", ".localhost")):
        return "Local or internal hosts are not allowed"
    return None

logger = logging.getLogger("osap.api.platform")

_CANONICALIZER: Canonicalizer | None
_NORMALIZER = MetadataNormalizer()
try:
    _CANONICALIZER = Canonicalizer(Path(__file__).resolve().parents[3] / "resources" / "canonical")
except Exception:
    _CANONICALIZER = None


def _summary(source: RepositorySource) -> RepositorySourceSummary:
    return RepositorySourceSummary(
        source_id=source.source_id,
        name=source.name,
        type=source.type,
        origin=source.origin,
        trust=source.trust,
        status=source.status,
        quality=source.quality,
        quality_label=source.quality_label,
        updated_at=source.updated_at,
    )


def _repository_source_from_defined(pid: str, name: str, base_url: str, wired: bool) -> RepositorySource:
    """Ficha completa de un proveedor definido en `providers/` (para el detalle)."""
    status = "Online" if wired else "Defined"
    return RepositorySource(
        source_id=pid,
        name=name,
        type="Provider",
        origin=_host_of(base_url),
        trust="Verified" if wired else "Community",
        status=status,
        quality=90 if wired else 50,
        quality_label="Excellent" if wired else "Pending",
        updated_at="",
        website=base_url,
        description=f"Proveedor {name} (definido en providers/{pid}).",
        notes="Definido, NO cableado como conector directo." if not wired else "Proveedor activo.",
        representations=0,
        works=0,
        composers=0,
    )


def _host_of(url: str) -> str:
    """Extract the host from a provider base URL (fallback to the raw URL)."""
    try:
        return urllib.parse.urlsplit(url).netloc or url
    except Exception:
        return url


_COLLECTION_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("symphon", "sinfon"), "Symphonies"),
    (("concerto", "konzert"), "Concertos"),
    (("sonata",), "Sonatas"),
    (("quartet", "trio", "quintet", "chamber"), "Chamber"),
    (("opera", "aria", "operatic", "zarzuela"), "Operas"),
    (
        (
            "missa", "requiem", "ave", "te deum", "magnificat", "mass",
            "hymn", "cantata", "chorale", "motet", "psalm", "sacred",
        ),
        "Sacred Music",
    ),    (("piano", "harpsichord", "clavier", "organ", "keyboard"), "Keyboard"),
)

def _classify_collection(title: str | None) -> str | None:
    """Asigna una colección a una obra a partir de su título (catalogación post-búsqueda).

    Es una clasificación ligera por palabras clave del título. Solo devuelve colecciones que
    existen en el lote; una obra sin coincidencia no recibe colección.
    """
    text = (title or "").lower()
    for keywords, collection in _COLLECTION_RULES:
        for keyword in keywords:
            if keyword in text:
                return collection
    return None


def _replace_provider_description(
    response: ProviderResponse, description: dict[str, str], website: str | None = None
) -> ProviderResponse:
    """Devuelve un ProviderResponse con la descripción multi-idioma y website (objeto frozen)."""
    return ProviderResponse(
        provider_id=response.provider_id,
        name=response.name,
        available=response.available,
        formats=list(response.formats),
        last_sync=response.last_sync,
        description=description,
        website=website,
    )


_PROVIDER_NAME_MAP = {
    "index": "index",
    "imslp": "imslp",
    "openscore": "openscore",
    "local": "local",
    "openmusicrepository": "omr",
    "open music repository": "omr",
    "omr": "omr",
    "mutopia": "mutopia",
    "musicbrainz": "musicbrainz",
    "rism": "rism",
    "cpdl": "cpdl",
}

# Etiquetas del bloque "Dónde" del Estudio (id -> opción). Cada opción debe resolverse
# de vuelta a su id con _provider_id_for_name.
_PROVIDER_OPTION_LABEL = {
    "imslp": "IMSLP",
    "openscore": "OpenScore",
    "omr": "OpenMusicRepository",
    "musicbrainz": "MusicBrainz",
    "mutopia": "Mutopia",
    "rism": "RISM",
    "cpdl": "CPDL",
}
_PROVIDER_OPTION_ORDER = ("imslp", "openscore", "omr", "musicbrainz", "mutopia", "rism", "cpdl")

# Opciones del bloque "Formación vocal" del Estudio. Son términos REALES observados en el
# corpus CPDL (cpdl_pages.voicing): no se inventan valores. El matching lo hace el
# proveedor CPDL contra cpdl_voicings con coincidencia exacta de token normalizado.
_STUDIO_VOICING_OPTIONS = [
    "SATB", "SATTB", "SSATB", "SSATTB", "SATB.SATB", "TTBB", "SAB", "SAATB",
    "ATTB", "STTB", "SSAA", "SSA", "TTB", "ATB", "SST", "SSB", "SATT", "SSAT",
    "TBB", "SA", "SS", "TT", "SAATTB", "SSAATTBB", "Unison", "Solo Soprano",
]

# Macro-familias de género (catálogo `genres` de osap-storage, semilla 040). El Estudio
# las ofrece como bloque "Género"; el backend las resuelve a su `genre_id` y el filtro
# solo se aplica en el índice local (obras OMR categorizadas). Espejo estático del
# catálogo: mantener sincronizado con la migración 040_genres.sql de osap-storage.
_STUDIO_GENRE_OPTIONS: list[tuple[int, str]] = [
    (1, "Música Clásica / Docta"),
    (2, "Música Sacra / Himnología"),
    (3, "Tradición Folclórica y Etnomusicología"),
    (4, "Jazz y Blues"),
    (5, "Rock y Metal"),
    (6, "Pop"),
    (7, "Música Urbana y Hip Hop"),
    (8, "Música Electrónica y Dance"),
    (9, "Música Latina y Caribeña"),
    (10, "Country, Folk y Americana"),
    (11, "Soul, Funk y Disco"),
    (12, "Música Escénica y Aplicada"),
]
_GENRE_ID_BY_NAME = {name: genre_id for genre_id, name in _STUDIO_GENRE_OPTIONS}


def _genre_id_for_name(name: str) -> int | None:
    """Resuelve el nombre visible de una macro-familia a su `genre_id` de osap-storage."""
    return _GENRE_ID_BY_NAME.get(name.strip())


def _studio_genre_names() -> list[str]:
    """Nombres de las macro-familias de género para el bloque "Género" del Estudio."""
    return [name for _, name in _STUDIO_GENRE_OPTIONS]


def _provider_id_for_name(name: str) -> str | None:
    key = name.strip().lower().replace("_", " ").replace("-", " ")
    return _PROVIDER_NAME_MAP.get(key) or _PROVIDER_NAME_MAP.get(key.replace(" ", ""))


_FORMAT_NAME_MAP = {
    "musicxml": "musicxml",
    "mxl": "musicxml",
    "xml": "musicxml",
    "pdf": "pdf",
    "midi": "midi",
    "mid": "midi",
    "ly": "ly",
    "kern": "kern",
}


def _format_for_name(name: str) -> str | None:
    key = name.strip().lower()
    return _FORMAT_NAME_MAP.get(key)


def _remote_online(url: str) -> bool:
    """True if the remote API responds; the OpenMusicRepository provider's availability
    is defined by its remote endpoint (api.openmusicrepository.com), not a local index.
    Any HTTP response counts as online (a Cloudflare 403 still means the server answers)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenMusicRepository health)"})
    try:
        with urllib.request.urlopen(req, timeout=4):  # noqa: S310 (trusted endpoint)
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


class KnowledgeStore:
    """In-memory read source for the Knowledge API (observations/facts/suggestions).

    Nota ADR-0035 (D3): se mantiene como lector sin alimentar hasta V3.3. El cableado de
    DefaultKnowledgeCollector/DefaultKnowledgeMiner tras cada sesión terminal de resolución
    está previsto para esa versión (aplicación humana de sugerencias, ADR-0027).
    """

    def __init__(self, base: KnowledgeBase | None = None) -> None:
        self._base = base or KnowledgeBase()

    def base(self) -> KnowledgeBase:
        return self._base

    def set_base(self, base: KnowledgeBase) -> None:
        self._base = base


class SourceCatalog:
    """In-memory catalog of permanent repository sources (V3.6.x Source Catalog)."""

    def __init__(self, sources: tuple[RepositorySource, ...] | None = None) -> None:
        self._sources = {s.source_id: s for s in (sources if sources is not None else _seed_sources())}

    def list(self) -> tuple[RepositorySource, ...]:
        return tuple(self._sources.values())

    def get(self, source_id: str) -> RepositorySource | None:
        return self._sources.get(source_id)


class SessionSources:
    """In-memory store of a user's temporary sources (Session Instances)."""

    def __init__(self) -> None:
        self._sources: dict[str, SessionSource] = {}
        self._counter = 0

    def create(self, name: str, source_type: str, location: str) -> SessionSource:
        self._counter += 1
        source = SessionSource(
            source_id=f"src-{self._counter}",
            name=name,
            type=source_type,
            location=location,
            status="CREATED",
            created_at=datetime.now(UTC).isoformat(),
        )
        self._sources[source.source_id] = source
        return source

    def get(self, source_id: str) -> SessionSource | None:
        return self._sources.get(source_id)

    def list(self) -> tuple[SessionSource, ...]:
        return tuple(self._sources.values())

    def forget(self, source_id: str) -> bool:
        return self._sources.pop(source_id, None) is not None

    def analyze(self, source_id: str) -> SessionSource | None:
        source = self._sources.get(source_id)
        if source is None:
            return None
        analysis = {"formats": ["MusicXML", "PDF"], "files": 0, "quality": "pending"}
        updated = SessionSource(
            source_id=source.source_id,
            name=source.name,
            type=source.type,
            location=source.location,
            status="ANALYZED",
            analysis=analysis,
            created_at=source.created_at,
        )
        self._sources[source_id] = updated
        return updated

    def use(self, source_id: str) -> SessionSource | None:
        source = self._sources.get(source_id)
        if source is None:
            return None
        updated = SessionSource(
            source_id=source.source_id,
            name=source.name,
            type=source.type,
            location=source.location,
            status="USED",
            analysis=source.analysis,
            created_at=source.created_at,
        )
        self._sources[source_id] = updated
        return updated


def _seed_sources() -> tuple[RepositorySource, ...]:
    return (
        RepositorySource(
            source_id="imslp",
            name="IMSLP",
            type="HTTP",
            origin="Official",
            trust="Verified",
            status="Online",
            quality=96,
            quality_label="Excellent",
            updated_at="2026-08-12 09:14 UTC",
            representations=128431,
            works=38912,
            composers=3281,
            formats=["MusicXML", "PDF", "MIDI"],
            catalogues=["BWV", "KV", "Hob.", "Op."],
            duplicate_percent=1.2,
            coverage=["Baroque", "Classical", "Romanticism"],
            capabilities=["Search", "Download", "MusicXML", "PDF", "MIDI", "Incremental Sync"],
            description="Official repository of public-domain scores.",
            license="Public Domain",
            website="https://imslp.org",
            contact="contact@imslp.org",
            notes="Very good Mozart coverage. PDFs before 2012 have low resolution.",
            observations=(
                SourceObservation(date="2026-07-18", text="Issues detected with Händel searches."),
                SourceObservation(date="2026-08-02", text="Provider is synchronized again."),
            ),
            tags=["Baroque", "Choral", "Critical Editions", "Public Domain", "Academic"],
            community_rating=4,
            reviews=27,
            searches=3214,
            downloads=9321,
            contributions=42,
            availability=99.8,
        ),
        RepositorySource(
            source_id="openscore",
            name="OpenScore",
            type="Git",
            origin="Community",
            trust="Community",
            status="Online",
            quality=88,
            quality_label="Good",
            updated_at="2026-08-11 18:02 UTC",
            representations=4123,
            works=1201,
            composers=640,
            formats=["MusicXML"],
            catalogues=["BWV", "KV"],
            duplicate_percent=0.4,
            coverage=["Baroque", "Classical"],
            capabilities=["Search", "Download", "MusicXML"],
            description="Community editions transcribed to MusicXML.",
            license="CC BY-SA",
            website="https://openscore.org",
            contact="",
            notes="",
            observations=(),
            tags=["Official", "Storage"],
            community_rating=0,
            reviews=0,
            searches=0,
            downloads=0,
            contributions=0,
            availability=100.0,
        ),
    )


_ARRANGEMENT_EXTRA = re.compile(
    r"^(\d{4}|kv|k|op|op\.|s|bwv|hob|d|cor|pf|vl|vla|vlc|org|coro|strings|sketches|"
    r"arr|arr\.|transcr|transc|ed|ed\.|v|vl|va|vc|fl|ob|cl|tr|hn|rec|guit|hp|accord|"
    r"choir|organ|piano|violin|viola|cello|flute|oboe|clarinet|trumpet|horn|harps|guitar|"
    r"satb|ssaa|ttbb|mixed|unison|st|nr|no|n)$"
)


def _is_arrangement_extra(extra: set[str]) -> bool:
    """True si todos los tokens extra de un título son marcadores de arreglo/edición."""
    return bool(extra) and all(bool(_ARRANGEMENT_EXTRA.match(t)) for t in extra)


def _title_core_match(core_tokens: set[str], title: str) -> bool:
    """True si el título conserva al menos la mitad de los tokens del núcleo de la obra."""
    if not core_tokens:
        return True
    title_tokens = set(str(title or "").lower().split())
    if not title_tokens:
        return False
    inter = len(core_tokens & title_tokens)
    return inter >= max(1, len(core_tokens) // 2)


def _search_signature(req: SearchRequest) -> str:
    """Firma estable de una búsqueda para el cache local (campos normalizados)."""
    return "|".join(
        [
            (req.query or "").strip().lower(),
            (req.composer or "").strip().lower(),
            (req.title or "").strip().lower(),
            (req.catalogue or "").strip().lower(),
            (req.instrumentation or "").strip().lower(),
            (req.language or "").strip().lower(),
            ",".join(sorted(f.lower() for f in req.formats)),
            ",".join(sorted(p.strip().lower() for p in req.providers)),
        ]
    )


def _download_bytes(url: str, timeout: int = 30) -> bytes:
    """Descarga el contenido de una URL (usado por el worker para validar MusicXML)."""
    req = urllib.request.Request(url, headers={"User-Agent": "osap-api/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw: bytes = resp.read()
        return raw


def _progress_flat(progress: dict[str, object]) -> dict[str, object]:
    """Normaliza el progress para el DTO: convierte escalares numéricos a int y
    conserva los valores anidados (dicts por provider) sin tocar."""
    out: dict[str, object] = {}
    for k, v in progress.items():
        if isinstance(v, (int, float, str)) and not isinstance(v, bool):
            try:
                out[k] = int(v)
                continue
            except (TypeError, ValueError):
                pass
        out[k] = v
    return out


def _selection_payload(selected: SelectedRepresentation) -> dict[str, object]:
    """Construye el payload estructurado de la representación seleccionada."""
    candidate = selected.candidate
    if candidate is None:
        return {"provider": None, "format": None, "quality_level": selected.quality_level.value}
    report = selected.report
    score_value = None
    if report is not None:
        overall = getattr(report, "overall", None)
        if callable(overall):
            try:
                score_value = round(float(overall()), 4)
            except Exception:  # noqa: BLE001
                score_value = None
    return {
        "provider": candidate.provider,
        "format": candidate.format,
        "source_id": candidate.source_id,
        "url": candidate.url,
        "title": candidate.title or "",
        "quality_level": selected.quality_level.value,
        "quality_score": score_value,
        "reason": selected.reason,
        "alternatives": [
            {"provider": a.provider, "format": a.format, "url": a.url} for a in selected.alternatives
        ],
        "warnings": list(selected.warnings),
    }


class _UnreadableScoreError(Exception):
    """La representación descargada no produce un Score legible."""


def _fetch_url_bytes(url: str) -> bytes | None:
    """Descarga bytes de la URL con User-Agent de cliente (igual criterio que el selector)."""
    import urllib.request

    try:
        req = urllib.request.Request(url, headers=browser_headers({"Accept": "*/*"}))
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw: bytes = resp.read()
            return raw
    except Exception:  # noqa: BLE001
        return None


def _validate_to_contract(content: bytes, identity: dict[str, object] | None) -> dict[str, object]:
    """Valida bytes MusicXML con el validador real y produce el `ScoreContract` (JSON).

    Reutiliza exactamente el mismo camino del pipeline (`BasicValidator` →
    `MusicXmlValidator` → `Score`) y el conversor establecido `score_to_contract`.
    """
    from src.chorus.contract.bridge import score_to_contract
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.musical_source import MusicalSource
    from src.osap.domain.quality_level import QualityLevel
    from src.osap.domain.value_objects import Confidence, Duration, SourceId
    from src.osap.infrastructure.adapters.validation import BasicValidator

    provider = str((identity or {}).get("provider") or "omr")
    source = MusicalSource(
        source_id=SourceId("score-contract"),
        content=content,
        format=OutputFormat.MUSICXML,
        metadata={
            "title": (identity or {}).get("title"),
            "composer": (identity or {}).get("composer"),
        },
    )
    acquisition = AcquisitionResult(
        provider_id=ProviderId(provider),
        source=source,
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=OutputFormat.MUSICXML,
    )
    try:
        score = BasicValidator().validate(acquisition)
    except Exception:  # noqa: BLE001 — fichero malformado = entrada no válida
        raise _UnreadableScoreError from None
    if score.quality_level == QualityLevel.UNREADABLE:
        raise _UnreadableScoreError
    return score_to_contract(score).to_dict()


_KNOWN_FORMATS_FALLBACK: dict[str, list[str]] = {
    "cpdl": ["pdf", "musicxml"],
    "imslp": ["pdf", "musicxml", "midi"],
    "mutopia": ["musicxml", "pdf", "midi"],
}


def _known_formats_for(provider_id: str) -> list[str]:
    return list(_KNOWN_FORMATS_FALLBACK.get(provider_id, []))


