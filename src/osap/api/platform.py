"""V3.1 — OSAP Platform API application layer.

Use cases exposed by the API. It calls existing Application Services (never domain
internals directly) and produces the public contract DTOs. Pure orchestration; no HTTP.
"""

import json
import logging
import os
import re
import secrets
import threading
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from src.osap.api.contracts import (
    CatalogueRead,
    DiscoverSource,
    IntentResponse,
    JobResponse,
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeResponse,
    KnowledgeSuggestionDTO,
    ProviderResponse,
    RepositorySource,
    RepositorySourceSummary,
    RepresentationInfo,
    SearchModel,
    SearchModelBlock,
    SearchModelCriteria,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SessionSource,
    SourceObservation,
    SourceSuggestionRead,
    SystemStatisticsResponse,
    SystemVersionResponse,
    WorkInfo,
    WorkRelationships,
)
from src.osap.application.canonicalizer import Canonicalizer
from src.osap.application.composer_resolution_engine import ResolutionDecision
from src.osap.application.composers_service import ComposersService
from src.osap.application.jobs import DefaultJob
from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.representation_selector import (
    RepresentationCandidate,
    SelectedRepresentation,
)
from src.osap.application.use_cases.resolve_works import ResolvedWorkItem, WorkResolveInput
from src.osap.application.votes_service import VotesService
from src.osap.bootstrap.container import Container
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.jobs import JobContext, JobTrigger
from src.osap.domain.knowledge import KnowledgeBase
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.principal import Principal
from src.osap.domain.resolve_request import ResolveRequestBuilder
from src.osap.domain.value_objects import ProviderId
from src.osap.domain.votes import ComposerStats, WorkStats, WorkVote
from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.provider_acquirer import CatalogAcquirer, IProviderAcquirer
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher
from src.osap.infrastructure.state.op_store import build_op_store
from src.osap.infrastructure.state.resolution_store import build_resolution_store
from src.osap.ports.composer_resolver import ResolverRepresentation

VERSION = "3.1"

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
    "imslp": "imslp",
    "openscore": "openscore",
    "local": "local",
    "openmusicrepository": "omr",
    "open music repository": "omr",
    "omr": "omr",
    "mutopia": "mutopia",
    "musicbrainz": "musicbrainz",
    "rism": "rism",
}


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
    """In-memory read source for the Knowledge API (observations/facts/suggestions)."""

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
        "quality_level": selected.quality_level.value,
        "quality_score": score_value,
        "reason": selected.reason,
        "alternatives": [
            {"provider": a.provider, "format": a.format, "url": a.url} for a in selected.alternatives
        ],
        "warnings": list(selected.warnings),
    }


class PlatformApi:
    """Use cases of the OSAP Platform API, backed by existing application services."""

    def __init__(
        self,
        container: Container,
        knowledge: KnowledgeStore | None = None,
        catalog: SourceCatalog | None = None,
    ) -> None:
        self._container = container
        self._knowledge = knowledge or KnowledgeStore()
        self._catalog = catalog or SourceCatalog()
        self._sessions = SessionSources()
        self._searches: dict[str, SearchResponse] = {}
        self._search_cache: dict[str, SearchResponse] = {}
        self._work_rep_cache: dict[str, list[RepresentationInfo]] = {}
        self._work_rep_order: list[str] = []
        self._jobs: dict[str, JobResponse] = {}
        self._representations: dict[str, dict[str, object]] = {}
        self._job_counter = 0
        self._oidc_pending: dict[str, dict[str, object]] = {}
        self._oidc_pending_path = os.environ.get("OSAP_OIDC_STATE_FILE") or ""
        self._oidc_pending_lock = threading.Lock()
        if self._oidc_pending_path:
            self._oidc_pending = self._load_oidc_pending()
        self._suggestion_counter = 0
        self._store = build_op_store(**(self._container.op_store_config() or {}))
        self._resolution_store = build_resolution_store(**(self._container.op_store_config() or {}))
        self._acquisition = self._build_acquisition_service()
        highest = 0
        for item in self._store.list_suggestions():
            sid = str(item.get("id") or "")
            if sid.startswith("sug-"):
                try:
                    highest = max(highest, int(sid[4:]))
                except ValueError:
                    continue
        self._suggestion_counter = highest + 1

    # --- search -------------------------------------------------------------

    def create_search(self, req: SearchRequest) -> tuple[str, SearchResponse]:
        search_id = uuid.uuid4().hex
        signature = _search_signature(req)
        cached = self._search_cache.get(signature)
        if cached is not None:
            page_results = self._paginate(cached.results, cached.total, req.page, req.limit)
            paginated = SearchResponse(
                search_id=search_id,
                results=page_results,
                total=cached.total,
                page=req.page,
                per_page=req.limit,
                status="done",
                progress=100,
                providers=list(cached.providers),
            )
            self._searches[search_id] = paginated
            return search_id, paginated
        # Búsqueda asíncrona: devuelve ya un recurso en "running"; el hilo lo completa.
        response = SearchResponse(search_id=search_id, status="running", progress=0)
        self._searches[search_id] = response

        def _run() -> None:
            provider_msgs: list[str] = []

            def _progress(p: int) -> None:
                self._searches[search_id] = SearchResponse(
                    search_id=search_id, status="running", progress=p, providers=list(provider_msgs)
                )

            def _provider(msg: str) -> None:
                if re.search(r"^\w+:\s*\d+ candidato", msg):
                    provider_msgs.append(msg)
                pv = min(60, 15 + len(provider_msgs) * 10)
                self._searches[search_id] = SearchResponse(
                    search_id=search_id, status="running", progress=pv, providers=list(provider_msgs)
                )

            def _partial(results: list[SearchResultItem], total: int) -> None:
                page_results = self._paginate(results, total, req.page, req.limit)
                self._searches[search_id] = SearchResponse(
                    search_id=search_id,
                    status="running",
                    progress=85,
                    results=page_results,
                    total=total,
                    page=req.page,
                    per_page=req.limit,
                    providers=list(provider_msgs),
                )

            try:
                results, total = self._run_search(req, _progress, _provider, _partial)
                page_results = self._paginate(results, total, req.page, req.limit)
                done = SearchResponse(
                    search_id=search_id,
                    results=page_results,
                    total=total,
                    page=req.page,
                    per_page=req.limit,
                    status="done",
                    progress=100,
                    providers=list(provider_msgs),
                )
                self._searches[search_id] = done
                # Cache del set COMPLETO (paginación instantánea y consistente).
                self._search_cache[signature] = SearchResponse(
                    search_id=search_id,
                    results=results,
                    total=total,
                    page=1,
                    per_page=max(1, total),
                    status="done",
                    progress=100,
                    providers=list(provider_msgs),
                )
            except Exception:  # noqa: BLE001
                logger.exception("search %s failed in background thread", search_id)
                failed = SearchResponse(
                    search_id=search_id, status="error", progress=100, providers=list(provider_msgs)
                )
                self._searches[search_id] = failed

        threading.Thread(target=_run, daemon=True).start()
        return search_id, response

    def get_search(self, search_id: str) -> SearchResponse | None:
        return self._searches.get(search_id)

    @staticmethod
    def _work_relationships(work: object) -> WorkRelationships:
        composer = str(getattr(work, "composer", "") or "")
        catalogue = str(getattr(work, "catalogue_number", "") or "")
        aliases: set[str] = set()
        related: list[str] = []
        if _CANONICALIZER is not None:
            if composer:
                canonical = _CANONICALIZER.canonicalize(composer).output
                aliases.update(a for a in _CANONICALIZER.aliases_for(canonical) if a)
            if catalogue:
                canonical_cat = _CANONICALIZER.canonicalize(catalogue).output
                related = [a for a in _CANONICALIZER.aliases_for(canonical_cat) if a]
        return WorkRelationships(
            aliases=sorted(aliases),
            related_catalogues=related,
            editions=[],
            parent_work=None,
            movements=[],
        )

    _COMPOSERS = (
        "mozart", "bach", "beethoven", "byrd", "poulenc", "handel", "vivaldi",
        "pachelbel", "palestrina", "monteverdi", "schubert", "haydn", "brahms", "chopin",
    )

    def detect_intent(self, query: str) -> IntentResponse:
        q = query.strip().lower()
        if re.search(r"(^|[\s,;])(kv|k\.?\s?\d+|bwv|op\.?\s?\d+|hob\.?|d\s?\d{3})", q):
            return IntentResponse(type="catalogue", label=query.strip())
        for composer in self._COMPOSERS:
            if re.search(rf"\b{re.escape(composer)}\b", q):
                # Quitar el compositor -> queda el título (si tiene palabras significativas).
                title_part = re.sub(rf"\b{re.escape(composer)}\b", " ", q)
                title_part = re.sub(r"\s+", " ", title_part).strip()
                if title_part and any(len(w) > 2 for w in title_part.split()):
                    return IntentResponse(
                        type="work", label=title_part, composer=composer.title()
                    )
                return IntentResponse(type="composer", label=composer.title())
        if "collection" in q or "edition" in q:
            return IntentResponse(type="collection", label=query.strip())
        return IntentResponse(type="work", label=query.strip())

    def search_model(self) -> SearchModel:
        return SearchModel(            blocks=[
                SearchModelBlock(
                    id="what",
                    label="WHAT",
                    kind="text",
                    criteria=[
                        SearchModelCriteria(key="title", label="Title"),
                        SearchModelCriteria(key="composer", label="Composer"),
                        SearchModelCriteria(key="catalogue", label="Catalogue"),
                        SearchModelCriteria(key="alias", label="Alias"),
                    ],
                ),
                SearchModelBlock(
                    id="where",
                    label="WHERE",
                    kind="multi",
                    options=["IMSLP", "OpenScore", "OpenMusicRepository", "MusicBrainz", "Mutopia", "RISM"],
                ),
                SearchModelBlock(
                    id="what_kind",
                    label="WHAT KIND",
                    kind="multi",
                    options=["MusicXML", "PDF", "MIDI"],
                ),
                SearchModelBlock(
                    id="quality",
                    label="QUALITY",
                    kind="range",
                    criteria=[SearchModelCriteria(key="confidence", label="Confidence")],
                ),
                SearchModelBlock(
                    id="options",
                    label="OPTIONS",
                    kind="boolean",
                    criteria=[
                        SearchModelCriteria(key="verified_only", label="Only verified"),
                        SearchModelCriteria(key="official_only", label="Only official"),
                    ],
                ),
            ]
        )

    def _run_search(
        self,
        req: SearchRequest,
        progress: Callable[[int], None] | None = None,
        on_provider: Callable[[str], None] | None = None,
        on_partial: Callable[[list[SearchResultItem], int], None] | None = None,
    ) -> tuple[list[SearchResultItem], int]:
        if progress is not None:
            progress(10)
        builder = ResolveRequestBuilder()
        composer_canonical = _NORMALIZER.canonical_composer(req.composer) if req.composer else req.composer
        if req.query:
            builder = builder.text(req.query)
        if composer_canonical:
            builder = builder.composer(composer_canonical)
        if req.title:
            builder = builder.title(req.title)
        if req.catalogue:
            builder = builder.catalogue(req.catalogue)
        if req.instrumentation:
            builder = builder.instrumentation(req.instrumentation)
        if req.language:
            builder = builder.language(req.language)
        # Filtros del Estudio: dónde (providers) y qué tipo (formats).
        if req.providers:
            for name in req.providers:
                pid = _provider_id_for_name(name)
                if pid:
                    builder = builder.allow_provider(ProviderId(pid))
        if req.formats:
            fmt = _format_for_name(req.formats[0])
            if fmt:
                builder = builder.format(OutputFormat(fmt))
        request = builder.build()
        logger.info(
            "search start query=%r composer=%r title=%r catalogue=%r",
            req.query,
            req.composer,
            req.title,
            req.catalogue,
        )
        engine = self._container.work_resolution_engine()

        def build_results(
            ranked: tuple[CandidateRepresentation, ...],
        ) -> tuple[list[SearchResultItem], int]:
            groups = list(self._container.work_merge_service().group(ranked))
            # Strict entity filters (providers may return loose matches for free-text).
            if composer_canonical:
                groups = [
                    g
                    for g in groups
                    if g.work.composer and composer_canonical.lower() in g.work.composer.lower()
                ]
            if req.title:
                groups = [g for g in groups if g.work.title and req.title.lower() in g.work.title.lower()]
            if req.catalogue:
                from src.osap.infrastructure.catalogs.index.index_catalog_provider import (
                    _catalogue_normalized,
                )

                cat_norm = _catalogue_normalized(req.catalogue)
                groups = [
                    g
                    for g in groups
                    if g.work.catalogue_number
                    and (
                        req.catalogue.lower() in g.work.catalogue_number.lower()
                        or (
                            cat_norm
                            and cat_norm
                            in _catalogue_normalized(g.work.catalogue_number)
                        )
                    )
                ]
            results: list[SearchResultItem] = []
            total = len(groups)
            for group in groups:
                work = group.work
                reps = []
                wanted_formats = (
                    {f for f in (_format_for_name(x) for x in req.formats) if f}
                    if req.formats
                    else None
                )
                wanted_pids = (
                    {p for p in (_provider_id_for_name(x) for x in req.providers) if p}
                    if req.providers
                    else None
                )
                for m in group.representations:
                    if m is not None:
                        rep = self._to_rep(m, work)
                        # Filtro del Estudio: qué tipo (formats) y dónde (providers).
                        if wanted_formats and rep.format not in wanted_formats:
                            continue
                        if wanted_pids and rep.provider not in wanted_pids:
                            continue
                        reps.append(rep)
                if not reps:
                    continue
                best = max(reps, key=lambda r: r.confidence)
                results.append(
                    SearchResultItem(
                        work=WorkInfo(
                            work_id=work.work_id.value,
                            title=work.title,
                            composer=work.composer,
                            catalogue=work.catalogue_number,
                            collection=_classify_collection(work.title),
                        ),
                        representation=best,
                        representations=reps,
                        score=best.confidence,
                        evidence=[],
                        relationships=self._work_relationships(work),
                    )
                )
            return results, total

        # Resultado parcial: publica lo que el índice ya encontró (a los ~1-3s),
        # mientras los providers en vivo siguen consultándose. La UI muestra esto
        # al instante y se refina cuando termina la búsqueda completa.
        index_partial: Callable[[tuple[CandidateRepresentation, ...]], None] | None = None
        if on_partial is not None:

            def index_partial(found: tuple[CandidateRepresentation, ...]) -> None:
                try:
                    partial, ptotal = build_results(found)
                    if partial:
                        on_partial(partial, ptotal)
                except Exception:  # noqa: BLE001
                    pass

        ranked = engine.rank(request, on_progress=on_provider, on_index_partial=index_partial)
        if progress is not None:
            progress(60)
        ranked_providers = sorted({c.provider_id.value for c in ranked})
        logger.info(
            "search ranked=%d providers=%s (openmusicrepository=%s)",
            len(ranked),
            ranked_providers,
            "openmusicrepository" in ranked_providers,
        )
        results, total = build_results(ranked)
        if progress is not None:
            progress(85)
        logger.info("search groups=%d", len(results))
        if on_partial is not None:
            on_partial(results, total)
        enriched = self._enrich_search_results(results, req.formats, req.providers)
        # total = obras que quedan tras el filtro de formatos/proveedores.
        filtered_total = len([r for r in enriched if r.representations])
        return enriched, filtered_total

    def _paginate(
        self, results: list[SearchResultItem], total: int, page: int, limit: int
    ) -> list[SearchResultItem]:
        start = (page - 1) * limit
        return results[start : start + limit]

    def _to_rep(self, m: object, work: object) -> RepresentationInfo:
        """Construye una RepresentationInfo a partir de un candidato (y la registra)."""
        fmt = getattr(m, "format", None)
        provider = getattr(m, "provider_id", None)
        confidence = getattr(m, "confidence", None)
        descriptor = getattr(m, "work_descriptor", None)
        download = getattr(m, "download_url", None)
        view = getattr(m, "view_url", None)
        provider_id = provider.value if provider is not None else ""
        # MusicBrainz solo tiene metadata (no fichero): no ofrecer descarga. El enlace
        # (url) apunta a la página web humana para "abrir en MusicBrainz".
        is_metadata_only = provider_id == "musicbrainz"
        # RISM/IMSLP/etc.: sin fichero directo -> available=False y url = página del
        # registro (p. ej. opac.rism.info) para "abrir en el proveedor".
        available = bool(download) and not is_metadata_only
        url = download or view
        rep_id = f"r-{uuid.uuid4().hex[:10]}"
        self._representations[rep_id] = {
            "download_url": download,
            "view_url": view,
            "composer": getattr(work, "composer", None),
            "title": getattr(work, "title", None),
            "catalogue": getattr(work, "catalogue_number", None),
            "format": fmt.value if fmt is not None else None,
        }
        return RepresentationInfo(
            id=rep_id,
            provider=provider_id,
            format=fmt.value if fmt is not None else "musicxml",
            confidence=confidence.value if confidence is not None else 0.0,
            title=str(getattr(descriptor, "title", None) or ""),
            url=url,
            available=available,
        )

    def _merge_same_work(self, results: list[SearchResultItem]) -> list[SearchResultItem]:
        """Fusiona en una línea las obras del mismo compositor que son arreglos/ediciones
        de la misma pieza ("Ave Verum Corpus" + "Ave Verum Corpus, Cor, Pf, KV 618, 1944").
        Regla: mismo compositor canónico + el título corto es subconjunto del largo y los
        tokens extra son marcadores de arreglo (año, catálogo, instrumentación, edición).
        """
        by_composer: dict[str, list[SearchResultItem]] = {}
        for item in results:
            comp = _NORMALIZER.canonical_composer(item.work.composer) if item.work.composer else ""
            by_composer.setdefault(comp, []).append(item)

        merged_out: list[SearchResultItem] = []
        for _comp, items in by_composer.items():
            items = list(items)
            consumed: set[int] = set()
            for i, a in enumerate(items):
                if i in consumed:
                    continue
                a_tok = set(_NORMALIZER.comparison_title(a.work.title or "", a.work.composer).split())
                union_reps = {r.id: r for r in a.representations}
                canonical = a
                for j in range(i + 1, len(items)):
                    if j in consumed:
                        continue
                    b = items[j]
                    b_tok = set(_NORMALIZER.comparison_title(b.work.title or "", b.work.composer).split())
                    if not a_tok or not b_tok:
                        continue
                    if a_tok <= b_tok and _is_arrangement_extra(b_tok - a_tok):
                        consumed.add(j)
                        for r in b.representations:
                            union_reps[r.id] = r
                    elif b_tok <= a_tok and _is_arrangement_extra(a_tok - b_tok):
                        consumed.add(j)
                        for r in b.representations:
                            union_reps[r.id] = r
                        if len(b_tok) < len(a_tok):
                            canonical = b
                reps = list(union_reps.values())
                best = max(reps, key=lambda r: r.confidence) if reps else canonical.representation
                merged_out.append(
                    SearchResultItem(
                        work=canonical.work,
                        representation=best,
                        representations=reps,
                        score=canonical.score,
                        evidence=canonical.evidence,
                        relationships=canonical.relationships,
                    )
                )
        merged_out.sort(key=lambda r: (-len(r.representations), (r.work.title or "").lower()))
        return merged_out

    def _work_key(self, title: str | None, composer: str | None) -> str:
        """Identidad normalizada de la obra (misma clave en cualquier query)."""
        core = _NORMALIZER.comparison_title(title or "", composer)
        comp = _NORMALIZER.canonical_composer(composer) if composer else ""
        return f"{core}|{comp}"

    def _enrich_search_results(
        self,
        results: list[SearchResultItem],
        formats: list[str] | None = None,
        providers: list[str] | None = None,
    ) -> list[SearchResultItem]:
        """Iguala las representaciones de cada obra usando el cache por obra.

        Una obra identificada (título+compositor normalizados) debe mostrar SIEMPRE las
        mismas representaciones, independientemente de la query ("mozart" == "ave verum").
        Las obras con representaciones de <5 providers se enriquecen con una búsqueda
        enfocada por título (una vez; el resultado queda cacheado). Se ordenan
        por nº de providers (las más infrarrepresentadas primero) con un tope por búsqueda.

        `formats`/`providers` (filtros del Estudio) se aplican sobre las representaciones
        finales de cada obra.
        """
        wanted_formats = (
            {f for f in (_format_for_name(x) for x in formats) if f} if formats else None
        )
        wanted_pids = (
            {p for p in (_provider_id_for_name(x) for x in providers) if p} if providers else None
        )

        def _filt(reps: list[RepresentationInfo]) -> list[RepresentationInfo]:
            if wanted_formats:
                reps = [r for r in reps if r.format in wanted_formats]
            if wanted_pids:
                reps = [r for r in reps if r.provider in wanted_pids]
            return reps

        results = self._merge_same_work(results)
        out: list[SearchResultItem] = []
        candidates_to_enrich: list[tuple[int, SearchResultItem]] = []
        for item in results:
            key = self._work_key(item.work.title, item.work.composer)
            current = {r.id: r for r in item.representations}
            cached = self._work_rep_cache.get(key)
            if cached is not None:
                for r in cached:
                    current[r.id] = r
            else:
                providers_now = {r.provider for r in item.representations}
                if len(providers_now) < 5:
                    candidates_to_enrich.append((len(providers_now), item))
            # Cache sin filtrar; el filtro del Estudio se aplica solo a la salida.
            reps_all = list(current.values())
            reps = _filt(reps_all)
            best = max(reps, key=lambda r: r.confidence) if reps else item.representation
            out.append(
                SearchResultItem(
                    work=item.work,
                    representation=best,
                    representations=reps,
                    score=item.score,
                    evidence=item.evidence,
                    relationships=item.relationships,
                )
            )
        candidates_to_enrich.sort(key=lambda x: (-len(x[1].representations), x[0]))
        for _nprov, item in candidates_to_enrich[:12]:
            key = self._work_key(item.work.title, item.work.composer)
            if key in self._work_rep_cache:
                continue
            focused = self._focused_representations(item.work)
            if not focused:
                continue
            merged = {r.id: r for r in item.representations}
            for r in focused:
                merged[r.id] = r
            reps_all = list(merged.values())
            self._cache_work_reps(key, reps_all)
            reps = _filt(reps_all)
            for it in out:
                if it.work.work_id == item.work.work_id:
                    best = max(reps, key=lambda r: r.confidence) if reps else it.representation
                    out[out.index(it)] = SearchResultItem(
                        work=it.work, representation=best, representations=reps,
                        score=it.score, evidence=it.evidence, relationships=it.relationships,
                    )
        return out

    def _cache_work_reps(self, key: str, reps: list[RepresentationInfo]) -> None:
        if key in self._work_rep_cache:
            self._work_rep_order.remove(key)
        self._work_rep_cache[key] = reps
        self._work_rep_order.append(key)
        if len(self._work_rep_order) > 2000:
            old = self._work_rep_order.pop(0)
            self._work_rep_cache.pop(old, None)

    def _focused_representations(self, work: WorkInfo) -> list[RepresentationInfo]:
        """Reúne las representaciones de una obra: búsqueda AMPLIA por título (sin
        filtro de compositor en la query, para captar todo) y filtra por título+compositor.

        El enrich se resuelve SOLO contra el índice local (offline): los proveedores
        indexados ya están en el índice, y RISM (no indexado) se consulta en vivo una
        sola vez en la búsqueda principal. Así no se dispara una búsqueda en vivo por
        cada obra a enriquecer.
        """
        core = _NORMALIZER.comparison_title(work.title or "", work.composer)
        ranked: tuple[object, ...] = ()
        try:
            request = ResolveRequestBuilder().title(core).online(False).build()
            ranked = self._container.work_resolution_engine().rank(request)
        except Exception:  # noqa: BLE001
            return []
        groups = list(self._container.work_merge_service().group(ranked))
        core_tokens = set((core or "").split())
        work_comp = _NORMALIZER.canonical_composer(work.composer) if work.composer else ""
        reps: list[RepresentationInfo] = []
        seen: set[tuple[str, str]] = set()
        for group in groups:
            for m in group.representations:
                t = (m.provider_id.value, str(getattr(m.work_descriptor, "title", None) or ""))
                if t in seen:
                    continue
                seen.add(t)
                if not _title_core_match(core_tokens, t[1]):
                    continue
                rep_composer = getattr(m.work_descriptor, "composer", None)
                rep_comp = _NORMALIZER.canonical_composer(rep_composer) if rep_composer else ""
                if work_comp and rep_comp and rep_comp != work_comp:
                    continue
                reps.append(self._to_rep(m, work))
        return reps

    def get_representation_download(self, representation_id: str) -> dict[str, object] | None:
        return self._representations.get(representation_id)

    # --- jobs ---------------------------------------------------------------

    def create_job(self, job_type: str) -> JobResponse:
        self._job_counter += 1
        job_id = f"job-{self._job_counter}"
        context = JobContext(
            execution_id=job_id,
            started_at=datetime.now(UTC),
            triggered_by=JobTrigger.API,
            dry_run=False,
        )
        result = DefaultJob().run(context)
        response = JobResponse(job_id=job_id, type=job_type, state=result.status.value, progress=100, result={})
        self._jobs[job_id] = response
        return response

    def list_jobs(self) -> list[JobResponse]:
        return sorted(self._jobs.values(), key=lambda job: job.job_id)

    def get_job(self, job_id: str) -> JobResponse | None:
        return self._jobs.get(job_id)

    # --- providers ----------------------------------------------------------

    def list_providers(self) -> list[ProviderResponse]:
        # `index` y `local` son proveedores internos (índice local / disco): no se
        # muestran como fuentes al usuario.
        responses = [
            self._provider_response(provider)
            for provider in self._container.catalog_manager().providers()
            if provider.provider_id.value not in ("index", "local")
        ]
        active_ids = {r.provider_id for r in responses}
        for pid, name, _base_url, wired in self._container.defined_providers():
            if pid in active_ids or pid in ("local", "index"):
                continue
            responses.append(
                ProviderResponse(provider_id=pid, name=name, available=wired, formats=[], last_sync=None)
            )
        # Descripción multi-idioma + website desde la BD operativa.
        try:
            enrich: dict[str, tuple[dict[str, str], str | None]] = {}
            for row in self._store.list_providers():
                pid = str(row.get("provider_id"))
                desc = row.get("description")
                clean: dict[str, str] = {}
                if isinstance(desc, dict):
                    clean = {str(k): str(v) for k, v in desc.items() if isinstance(v, str)}
                base_url = row.get("base_url")
                website = str(base_url) if base_url else None
                if clean or website:
                    enrich[pid] = (clean, website)
        except Exception:  # noqa: BLE001
            enrich = {}
        for i, r in enumerate(responses):
            if r.provider_id in enrich:
                clean, website = enrich[r.provider_id]
                responses[i] = _replace_provider_description(r, clean, website)
        return responses

    def get_provider(self, provider_id: str) -> ProviderResponse | None:
        for provider in self._container.catalog_manager().providers():
            if provider.provider_id.value == provider_id:
                return self._provider_response(provider)
        return None

    @staticmethod
    def _provider_response(provider: object) -> ProviderResponse:
        capabilities = provider.capabilities()  # type: ignore[attr-defined]
        availability = str(capabilities.metadata.get("availability") or "")
        available = availability != "index_missing"
        info = provider.metadata()  # type: ignore[attr-defined]
        provider_id = provider.provider_id.value  # type: ignore[attr-defined]
        name = "OpenMusicRepository" if provider_id == "openmusicrepository" else info.name
        if provider_id == "openmusicrepository":
            # The OpenMusicRepository provider is the storage repository: online if its
            # Provider API (version endpoint) responds.
            available = _remote_online("https://storage.openmusicrepository.com/api/v1/health")
        return ProviderResponse(
            provider_id=provider_id,
            name=name,
            available=available,
            formats=[f.value for f in capabilities.formats],
            last_sync=None,
        )

    # --- votes & statistics (v1) --------------------------------------------

    def votes(self) -> VotesService:
        return self._container.votes_service()

    def principal_for(self, token: str | None) -> Principal | None:
        return self.votes().principal_for(token)

    def current_user(self, token: str | None) -> Principal | None:
        return self.principal_for(token)

    def require_can_vote(self, token: str | None) -> Principal:
        return self.votes().require_can_vote(token)

    def require_admin(self, token: str | None) -> Principal:
        return self.votes().require_admin(token)

    def cast_vote(self, token: str | None, work_id: str, vote: int) -> WorkVote:
        return self.votes().cast_vote(token, work_id, vote)

    def work_statistics(self, work_id: str) -> WorkStats:
        return self.votes().work_statistics(work_id)

    def composer_statistics(self, composer_id: str) -> ComposerStats:
        return self.votes().composer_statistics(composer_id)

    def votes_overview(self) -> dict[str, object]:
        return self.votes().overview()

    # --- registro / verificación de usuario (proxy a osap-auth) --------------

    def register_user(self, email: str, password: str, name: str | None = None) -> tuple[int, dict[str, object]]:
        return self._container.auth_proxy().register(email, password, name)

    def verify_email(self, token: str) -> tuple[int, dict[str, object]]:
        return self._container.auth_proxy().verify_email(token)

    # --- compositores (consulta pública + fusión admin) ----------------------

    def composers(self) -> ComposersService:
        return self._container.composers_service()

    def list_composers(
        self, q: str | None, limit: int, offset: int, review: str | None = None
    ) -> dict[str, object]:
        return self.composers().list_composers(q, limit, offset, review)

    def get_composer(self, composer_id: str) -> dict[str, object] | None:
        return self.composers().get_composer(composer_id)

    def get_composer_biography(self, composer_id: str) -> dict[str, object] | None:
        return self.composers().get_composer_biography(composer_id)

    def composer_works(self, composer_id: str, limit: int, offset: int) -> dict[str, object]:
        return self.composers().composer_works(composer_id, limit, offset)

    def get_work(self, work_id: str) -> dict[str, object] | None:
        return self.composers().get_work(work_id)

    def merge_composers(self, token: str | None, target_id: str, source_ids: list[str]) -> dict[str, object]:
        return self.composers().merge_composers(token, target_id, source_ids)

    def create_composer(self, token: str | None, name: str) -> dict[str, object]:
        return self.composers().create_composer(token, name)

    def review_composer(self, token: str | None, composer_id: str, review_status: str) -> dict[str, object]:
        return self.composers().review_composer(token, composer_id, review_status)

    def add_alias(self, token: str | None, composer_id: str, alias: str) -> dict[str, object]:
        return self.composers().add_alias(token, composer_id, alias)

    def list_aliases(self, token: str | None, composer_id: str) -> list[dict[str, object]]:
        return self.composers().list_aliases(token, composer_id)

    def move_alias(
        self, token: str | None, alias_id: int, from_composer_id: str, target_composer_id: str
    ) -> dict[str, object]:
        return self.composers().move_alias(token, alias_id, from_composer_id, target_composer_id)

    def promote_alias(self, token: str | None, composer_id: str, alias_id: int) -> dict[str, object]:
        return self.composers().promote_alias(token, composer_id, alias_id)

    def set_attribution(self, token: str | None, composer_ids: list[str], attribution_type: str) -> dict[str, object]:
        return self.composers().set_attribution(token, composer_ids, attribution_type)

    async def resolve_composer(
        self,
        work_title: str,
        composer: str | None = None,
        work_catalog: str | None = None,
        work_year: int | None = None,
        source_provider: str | None = None,
        source_work_id: str | None = None,
        representations: list[dict[str, str]] | None = None,
    ) -> ResolutionDecision:
        reps = [
            ResolverRepresentation(title=r["title"], provider=r["provider"], format=r["format"])
            for r in representations or []
        ]
        use_case = self._container.composer_resolution()
        return await use_case.execute(
            composer=composer,
            work_title=work_title,
            work_catalog=work_catalog,
            work_year=work_year,
            source_provider=source_provider,
            source_work_id=source_work_id,
            representations=reps,
        )

    async def works_resolve(
        self,
        works: list[dict[str, object]],
        concurrency: int = 4,
    ) -> list[ResolvedWorkItem]:
        inputs: list[WorkResolveInput] = []
        for w in works:
            work = cast("dict[str, object]", w.get("work") or {})
            composer = cast("dict[str, object]", w.get("composer") or {})
            source = cast("dict[str, object]", w.get("source") or {})
            inputs.append(
                WorkResolveInput(
                    id=str(w["id"]) if w.get("id") is not None else None,
                    composer=cast("str | None", composer.get("name")) if composer else None,
                    work_title=cast("str | None", work.get("title")),
                    work_catalog=cast("str | None", work.get("catalog")),
                    work_year=cast("int | None", work.get("year")),
                    source_provider=cast("str | None", source.get("provider")) if source else None,
                    source_work_id=cast("str | None", source.get("source_work_id")) if source else None,
                )
            )
        return await self._container.works_resolution().execute(inputs, concurrency)

    # --- resolution sessions (ADR-0033) ---------------------------------------

    _DEFAULT_PROVIDERS = ["omr", "imslp", "musicbrainz", "mutopia"]
    _DEFAULT_POLICY = {
        "max_results_to_acquire": 500,
        "max_pages_per_provider": 20,
        "max_duration_s": 120,
        "ttl_s": 1800,
    }

    def create_resolution_session(
        self,
        query: str | None = None,
        works: list[dict[str, object]] | None = None,
        providers: list[str] | None = None,
        policy: dict[str, object] | None = None,
    ) -> dict[str, object]:
        resolved_policy = {**self._DEFAULT_POLICY, **(policy or {})}
        resolved_providers = providers or list(self._DEFAULT_PROVIDERS)
        session_id = f"ses_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        ttl = int(cast("int", resolved_policy.get("ttl_s", 1800)))
        created_at = now.isoformat()
        expires_at = (now + timedelta(seconds=ttl)).isoformat()
        query_json = json.dumps({"query": query, "works": works or []}, ensure_ascii=False)
        providers_json = json.dumps(resolved_providers, ensure_ascii=False)
        policy_json = json.dumps(resolved_policy, ensure_ascii=False)
        self._resolution_store.create_session(
            session_id, query_json, providers_json, policy_json, created_at, expires_at
        )
        return {
            "session_id": session_id,
            "status": "acquiring",
            "created_at": created_at,
            "expires_at": expires_at,
        }

    def set_acquisition_acquirers(self, acquirers: dict[str, IProviderAcquirer]) -> None:
        """Inyecta los acquirers de proveedor (normalmente por wiring)."""
        self._acquisition = AcquisitionService(self._resolution_store, acquirers, SimpleUniverseMatcher())

    def _build_acquisition_service(self) -> AcquisitionService:
        """Construye el AcquisitionService con acquirers reales sobre el catálogo.

        Reutiliza los providers ya wireados en el container (RemoteCatalogProvider, ...)
        vía `CatalogAcquirer`: el pipeline de resolución consulta exactamente los mismos
        providers que la búsqueda productiva, sin duplicar HTTP ni mapping.
        """
        acquirers: dict[str, IProviderAcquirer] = {}
        for provider in self._container.catalog_manager().providers():
            pid = provider.provider_id.value
            if pid in ("local", "index"):
                # Los proveedores internos no se consultan en vivo para una sesión de
                # resolución (el índice/local ya alimentan la búsqueda normal).
                continue
            acquirers[pid] = CatalogAcquirer(pid, provider)
        return AcquisitionService(self._resolution_store, acquirers, SimpleUniverseMatcher())

    def resolve_session(self, session_id: str) -> str | None:
        """Ejecuta una sesión hasta su estado terminal (completa adquisición + matching
        definitivo) y valida la mejor representación descargable obtenida.

        Devuelve el estado final (`complete`/`partial`/`expired`), o None si la sesión
        no existe. La validación (BasicValidator → Score + QualityReport + PipelineLog)
        se registra en el estado de la sesión vía `error`/metadata.
        """
        row = self._resolution_store.get_session(session_id)
        if row is None:
            return None
        status = self._acquisition.run_until_terminal(session_id)
        if status in ("complete", "partial"):
            self._validate_best_representation(session_id, status)
        return status

    def _validate_best_representation(self, session_id: str, status: str) -> None:
        """Selecciona y valida la mejor representación adquirida.

        Recoge TODAS las representaciones descargables, las valida con el
        `BestRepresentationSelector` (MusicXmlValidator) y persiste la selección en
        `selection_json` (resultado normal). `error` se usa SOLO para fallos reales.
        """
        from src.osap.application.representation_selector import BestRepresentationSelector

        candidates = self._all_downloadable(session_id)
        if not candidates:
            self._resolution_store.update_status(
                session_id, status, error="sin representación descargable para validar"
            )
            return
        selected = BestRepresentationSelector().select(candidates)
        if selected.candidate is None:
            detail = "; ".join(selected.errors) if selected.errors else selected.reason
            self._resolution_store.update_status(session_id, status, error=f"validación: {detail}")
            return
        selection = _selection_payload(selected)
        self._resolution_store.set_selection(session_id, json.dumps(selection, ensure_ascii=False))

    def _all_downloadable(self, session_id: str) -> tuple[RepresentationCandidate, ...]:
        """Todas las representaciones descargables de la sesión (para el selector)."""
        out: list[RepresentationCandidate] = []
        for row in self._resolution_store.list_all_provider_results(session_id):
            try:
                works = json.loads(str(row.get("payload_json") or "[]"))
            except ValueError:
                continue
            provider = str(row.get("provider") or "unknown")
            for work in works:
                if not isinstance(work, dict):
                    continue
                for resource in work.get("resources") or []:
                    if not isinstance(resource, dict):
                        continue
                    links = resource.get("links") or {}
                    url = str(links.get("download") or "")
                    if not url.startswith(("http://", "https://")):
                        continue
                    out.append(
                        RepresentationCandidate(
                            provider=provider,
                            format=str(resource.get("format") or "unknown"),
                            url=url,
                            source_id=f"{session_id}-{provider}-{len(out)}",
                        )
                    )
        return tuple(out)

    def _best_downloadable(self, session_id: str) -> tuple[str | None, str | None]:
        """Mejor representación descargable entre los provider_results adquiridos.

        Prioriza representaciones con fichero real (MusicXML/MXL/MEI) sobre páginas de
        proveedor (IMSLP/MusicBrainz apuntan al registro humano, no al fichero). Entre
        iguales, la primera URL encontrada gana.
        """
        score_formats = {"musicxml", "mxl", "mei"}
        best_url: str | None = None
        best_format: str | None = None
        best_score = 0
        for row in self._resolution_store.list_all_provider_results(session_id):
            try:
                works = json.loads(str(row.get("payload_json") or "[]"))
            except ValueError:
                continue
            for work in works:
                if not isinstance(work, dict):
                    continue
                for resource in work.get("resources") or []:
                    if not isinstance(resource, dict):
                        continue
                    links = resource.get("links") or {}
                    url = str(links.get("download") or "")
                    if not url.startswith(("http://", "https://")):
                        continue
                    fmt = str(resource.get("format") or "").lower()
                    score = 2 if fmt in score_formats else 1
                    if score > best_score:
                        best_score = score
                        best_url = url
                        best_format = fmt
        return best_url, best_format

    def run_resolution_worker(self, max_sessions: int = 1) -> list[str]:
        """Recoge y procesa sesiones `acquiring` (una unidad de trabajo por sesión)."""
        statuses: list[str] = []
        while len(statuses) < max_sessions:
            session_id = self._acquisition.next_session_id()
            if session_id is None:
                break
            statuses.append(self._acquisition.run_until_terminal(session_id))
        return statuses

    def get_resolution_session(self, session_id: str) -> dict[str, object] | None:
        row = self._resolution_store.get_session(session_id)
        if row is None:
            return None
        return self._resolution_session_row(row)

    def list_resolution_results(
        self, session_id: str, page: int = 1, per_page: int = 25
    ) -> dict[str, object] | None:
        row = self._resolution_store.get_session(session_id)
        if row is None:
            return None
        offset = max(0, (int(page) - 1) * int(per_page))
        rows, total = self._resolution_store.list_results(session_id, offset, int(per_page))
        status = str(row.get("status") or "acquiring")
        resolution_stage = "definitive" if status in ("complete", "partial", "failed", "expired") else "provisional"
        revision = max((int(cast("int", r.get("revision") or 0)) for r in rows), default=0)
        return {
            "session_id": session_id,
            "status": status,
            "resolution_stage": resolution_stage,
            "revision": revision,
            "page": int(page),
            "per_page": int(per_page),
            "total": total,
            "results": [self._resolution_item_row(r) for r in rows],
        }

    @staticmethod
    def _resolution_session_row(row: dict[str, object]) -> dict[str, object]:
        query_info = json.loads(str(row.get("query_json") or "{}"))
        progress_raw = json.loads(str(row.get("progress_json") or "{}"))
        selection_raw = row.get("selection_json")
        try:
            selection = json.loads(str(selection_raw)) if selection_raw else None
        except ValueError:
            selection = None
        return {
            "session_id": str(row["session_id"]),
            "status": str(row.get("status") or "acquiring"),
            "query": query_info.get("query"),
            "providers": json.loads(str(row.get("providers_json") or "[]")),
            "policy": json.loads(str(row.get("policy_json") or "{}")),
            # El progress puede tener claves anidadas (p. ej. `providers` -> dict por
            # provider) además de contadores planos; se devuelve tal cual.
            "progress": _progress_flat(progress_raw),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
            "expires_at": str(row.get("expires_at") or ""),
            "error": row.get("error"),
            "selection": selection,
        }

    @staticmethod
    def _resolution_item_row(row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "status": str(row.get("status") or "not_found"),
            "resolution_stage": str(row.get("resolution_stage") or "provisional"),
            "revision": int(cast("int", row.get("revision") or 1)),
            "normalized": json.loads(str(row.get("normalized_json") or "null")) if row.get("normalized_json") else None,
            "resolved": json.loads(str(row.get("resolved_json") or "null")) if row.get("resolved_json") else None,
            "confidence": float(cast("float", row.get("confidence") or 0.0)),
            "input_quality": str(row.get("input_quality") or "normal"),
            "candidates": json.loads(str(row.get("candidates_json") or "[]")),
            "evidence": json.loads(str(row.get("evidence_json") or "[]")),
        }

    def composer_review_stats(self, token: str | None) -> dict[str, int]:
        stats = self.composers().composer_review_stats(token)
        # Estados reales: `reviewed`/`not_reviewed`/`review_required` (puestos por el
        # proceso de biografías) + `correct`/`incorrect` (clasificación manual/IA antigua).
        reviewed = int(stats.get("reviewed") or 0) + int(stats.get("correct") or 0) + int(stats.get("incorrect") or 0)
        not_reviewed = int(stats.get("not_reviewed") or 0)
        review_required = int(stats.get("review_required") or 0)
        total = reviewed + not_reviewed + review_required
        return {
            "total": total,
            "correct": int(stats.get("correct") or 0),
            "incorrect": int(stats.get("incorrect") or 0),
            "reviewed": reviewed,
            "not_reviewed": not_reviewed + review_required,
        }

    def catalogues(self, prefix: str | None = None, composer: str | None = None) -> list[CatalogueRead]:
        rows = self.composers().catalogues(prefix, composer)
        out: list[CatalogueRead] = []
        for row in rows:
            out.append(
                CatalogueRead(
                    id=int(str(row.get("id") or 0)),
                    prefix=str(row.get("prefix") or ""),
                    composer=str(row.get("composer") or ""),
                    catalogue_name=str(row.get("catalogue_name") or ""),
                    creator=str(row.get("creator") or ""),
                    ordering_criterion=str(row.get("ordering_criterion") or ""),
                )
            )
        return out

    def storage_web(self, token: str | None) -> str:
        self._require_admin(token)
        base = (self._container.storage_web_base() or self.composers().storage_base_url()).rstrip("/")
        if self._container.dev_auth_bypass():
            service_token = secrets.token_urlsafe(16)
        else:
            service_token = self.composers().storage_admin_token()
        return f"{base}/admin?token={urllib.parse.quote(service_token)}"

    def admin_overview(self, token: str | None) -> dict[str, object]:
        stats = self.composer_review_stats(token)
        suggestions = self._store.suggestion_counts()
        storage = self.composers().storage_statistics()
        return {
            "composers": stats,
            "source_suggestions_pending": suggestions.get("pending", 0),
            "source_suggestions": suggestions,
            "storage": storage,
        }

    # --- proveedores dinámicos + config (BD operativa) -----------------------

    def list_op_providers(self, token: str | None) -> list[dict[str, object]]:
        self._require_admin(token)
        return self._store.list_providers()

    def upsert_op_provider(
        self,
        token: str | None,
        provider_id: str,
        name: str,
        base_url: str | None,
        wired: bool,
        config: dict[str, object],
        description: dict[str, str] | None = None,
        endpoints: dict[str, object] | None = None,
        mapping: dict[str, object] | None = None,
        resources: dict[str, object] | None = None,
        transforms: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self._require_admin(token)
        return self._store.upsert_provider(
            provider_id, name, base_url=base_url, wired=wired, kind="dynamic",
            config=config, description=description, endpoints=endpoints,
            mapping=mapping, resources=resources, transforms=transforms,
        )

    def delete_op_provider(self, token: str | None, provider_id: str) -> bool:
        self._require_admin(token)
        return self._store.delete_provider(provider_id)

    def set_op_provider_wired(self, token: str | None, provider_id: str, wired: bool) -> dict[str, object] | None:
        self._require_admin(token)
        return self._store.set_provider_wired(provider_id, wired)

    def get_op_config(self, token: str | None) -> dict[str, object]:
        self._require_admin(token)
        out: dict[str, object] = {}
        for key in (
            "deployment",
            "dev_mode",
            "imslp_base_url",
            "library_root",
            "default_output_format",
            "default_quality_level",
        ):
            value = self._store.get_config(key)
            if value is not None:
                out[key] = value
        return out

    def set_op_config(self, token: str | None, key: str, value: str) -> dict[str, object]:
        self._require_admin(token)
        self._store.set_config(key, value)
        return {"key": key, "value": value}

    # --- knowledge (read-only) ----------------------------------------------

    def knowledge(self) -> KnowledgeResponse:
        base = self._knowledge.base()
        return KnowledgeResponse(
            observations=[
                KnowledgeObservationDTO(
                    execution_id=o.execution_id,
                    source=o.source.value,
                    field=o.field,
                    value=o.value,
                    provider=o.provider,
                )
                for o in base.observations
            ],
            facts=[
                KnowledgeFactDTO(fact_type=f.fact_type.value, field=f.field, value=f.value, count=f.count)
                for f in base.facts
            ],
            suggestions=[
                KnowledgeSuggestionDTO(
                    suggestion_type=s.suggestion_type.value,
                    field=s.field,
                    source_value=s.source_value,
                    target_value=s.target_value,
                    reason=s.reason,
                )
                for s in base.suggestions
            ],
        )

    # --- system -------------------------------------------------------------

    def health(self) -> str:
        return "ok"

    def storage_info(self) -> tuple[str, bool]:
        return self._container.storage_info()

    # --- bypass de desarrollo (SOLO dev; activado por OSAP_DEV_AUTH_BYPASS=1) ---

    def dev_auth_bypass(self) -> bool:
        return self._container.dev_auth_bypass()

    def dev_session(self) -> dict[str, object]:
        """Sesión admin de desarrollo. `JwtAuthenticator` en dev decodifica sin firma;
        este endpoint NUNCA debe activarse en producción (OSAP_DEV_AUTH_BYPASS)."""
        from src.osap.domain.votes import ForbiddenError

        if not self._container.dev_auth_bypass():
            raise ForbiddenError("Dev auth bypass not enabled")
        import base64

        def _b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
        payload = _b64(
            json.dumps(
                {
                    "sub": "dev-admin",
                    "token_use": "user",
                    "roles": ["user", "admin"],
                    "email_verified": True,
                    "aud": "osap-api",
                }
            ).encode("utf-8")
        )
        return {
            "access_token": f"{header}.{payload}.",
            "refresh_token": "dev-refresh-token",
            "token_type": "Bearer",
            "expires_in": 86400,
        }

    # --- OIDC (login vía osap-auth como IdP) --------------------------------

    def _load_oidc_pending(self) -> dict[str, dict[str, object]]:
        """Recupera los estados OIDC pendientes desde disco (sobreviven a reinicios)."""
        try:
            with open(self._oidc_pending_path, encoding="utf-8") as fh:
                data = json.load(fh)
            return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _persist_oidc_pending(self) -> None:
        """Persiste los estados pendientes en disco (best-effort, nunca bloquea el login)."""
        if not self._oidc_pending_path:
            return
        try:
            with open(self._oidc_pending_path, "w", encoding="utf-8") as fh:
                json.dump(self._oidc_pending, fh)
        except OSError:
            pass

    def oidc_start(self) -> dict[str, object]:
        from src.osap.infrastructure.auth.oidc_rp_client import OidcError

        oidc = self._container.oidc_client()
        if not oidc.configured():
            raise OidcError("OIDC no configurado")
        verifier, challenge = oidc.generate_pkce()
        state = oidc.generate_state()
        nonce = oidc.generate_state()
        with self._oidc_pending_lock:
            self._oidc_pending[state] = {
                "verifier": verifier,
                "nonce": nonce,
                "created_at": datetime.now(UTC).timestamp(),
            }
            self._persist_oidc_pending()
        authorize_url = oidc.build_authorize_url(state, nonce, challenge)
        return {"authorize_url": authorize_url, "configured": True}

    def oidc_error_url(self, message: str) -> str:
        return self._container.oidc_client().error_callback_url(message)

    def oidc_callback(self, code: str | None, state: str | None) -> str:
        from src.osap.infrastructure.auth.oidc_rp_client import OidcError

        oidc = self._container.oidc_client()
        with self._oidc_pending_lock:
            if not state or state not in self._oidc_pending:
                raise OidcError("OIDC state inválido o ausente")
            pending = self._oidc_pending.pop(state)
            self._persist_oidc_pending()
        created = float(str(pending.get("created_at") or 0))
        if datetime.now(UTC).timestamp() - created > 1800:
            raise OidcError("OIDC state caducado")
        if not code:
            raise OidcError("OIDC code ausente")
        tokens = oidc.exchange_code(code, str(pending["verifier"]))
        access = str(tokens.get("access_token") or "")
        refresh = str(tokens.get("refresh_token") or "")
        if not access:
            raise OidcError("OIDC no devolvió access_token")
        return oidc.spa_callback_url(access, refresh)

    def version(self) -> SystemVersionResponse:
        return SystemVersionResponse(version=VERSION)

    # --- repository sources (Source Catalog) --------------------------------

    def list_repository_sources(self) -> list[RepositorySourceSummary]:
        summaries = [_summary(s) for s in self._catalog.list()]
        seen = {s.source_id for s in summaries}
        for pid, name, base_url, wired in self._container.defined_providers():
            if pid in seen or pid == "local":
                continue
            summaries.append(
                RepositorySourceSummary(
                    source_id=pid,
                    name=name,
                    type="Provider",
                    origin=_host_of(base_url),
                    trust="Verified" if wired else "Community",
                    status="Online" if wired else "Defined",
                    quality=90 if wired else 50,
                    quality_label="Excellent" if wired else "Pending",
                    updated_at="",
                )
            )
            seen.add(pid)
        return summaries

    def get_repository_source(self, source_id: str) -> RepositorySource | None:
        seeded = self._catalog.get(source_id)
        if seeded is not None:
            return seeded
        for pid, name, base_url, wired in self._container.defined_providers():
            if pid == source_id and pid != "local":
                return _repository_source_from_defined(pid, name, base_url, wired)
        return None

    # --- session sources (user's temporary sources) -------------------------

    def create_session_source(self, name: str, source_type: str, location: str) -> SessionSource:
        return self._sessions.create(name, source_type, location)

    def list_session_sources(self) -> list[SessionSource]:
        return list(self._sessions.list())

    def get_session_source(self, source_id: str) -> SessionSource | None:
        return self._sessions.get(source_id)

    def forget_session_source(self, source_id: str) -> bool:
        return self._sessions.forget(source_id)

    def analyze_session_source(self, source_id: str) -> SessionSource | None:
        return self._sessions.analyze(source_id)

    def use_session_source(self, source_id: str) -> SessionSource | None:
        return self._sessions.use(source_id)

    # --- fuente propuesta por un usuario (Añadir fuente) --------------------

    def preview_source(self, url: str) -> tuple[bool, list[str], str | None]:
        """Intenta leer el fichero de la URL y adivinar los campos (mapping).

        Es best-effort: si no se puede leer o no es JSON, devuelve error sin romper
        el flujo. Los campos son las claves de primer nivel más las de una muestra
        de elementos (works/items/results/data/files).
        """
        if not url:
            return False, [], "Provide a URL"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenMusicRepository)"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (user-provided source URL)
                raw = resp.read(2_000_000)
        except Exception as exc:  # noqa: BLE001
            return False, [], f"Could not read URL: {exc}"
        try:
            import json

            doc = json.loads(raw)
        except Exception:  # noqa: BLE001
            return False, [], "The URL does not contain valid JSON"
        if not isinstance(doc, dict):
            return False, [], "Expected a JSON object"
        fields = [k for k in doc if isinstance(k, str)]
        for arr_key in ("works", "items", "results", "data", "files", "scores"):
            value = doc.get(arr_key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                for k in value[0]:
                    if isinstance(k, str) and k not in fields:
                        fields.append(k)
        return True, fields, None

    def suggest_source(
        self,
        token: str | None,
        name: str,
        source_type: str,
        location: str,
        mapping: dict[str, object],
    ) -> SourceSuggestionRead:
        principal = self._container.authenticator().resolve(token)
        if principal is None or not getattr(principal, "user_id", None):
            from src.osap.domain.votes import UnauthenticatedError

            raise UnauthenticatedError("Login required to suggest a source")
        user = str(getattr(principal, "user_id", "anonymous"))
        self._suggestion_counter += 1
        suggestion_id = f"sug-{self._suggestion_counter}"
        row = self._store.add_suggestion(
            suggestion_id,
            name,
            source_type,
            location,
            dict(mapping),
            user,
        )
        suggestion = SourceSuggestionRead(
            id=str(row["id"]),
            name=str(row["name"]),
            type=str(row["type"]),
            location=str(row["location"]),
            mapping=json.loads(str(row["mapping"])),
            requested_by=str(row["requested_by"]),
            status=str(row["status"]),
            admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
            created_at=str(row["created_at"]),
        )
        # En esta sesión se incluye en los resultados de búsqueda.
        self._sessions.create(name, source_type, location)
        return suggestion

    def list_source_suggestions(self, token: str | None) -> list[SourceSuggestionRead]:
        self._require_admin(token)
        result: list[SourceSuggestionRead] = []
        for row in self._store.list_suggestions():
            result.append(
                SourceSuggestionRead(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    type=str(row["type"]),
                    location=str(row["location"]),
                    mapping=json.loads(str(row["mapping"])),
                    requested_by=str(row["requested_by"]),
                    status=str(row["status"]),
                    admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
                    created_at=str(row["created_at"]),
                )
            )
        return result

    def resolve_source_suggestion(
        self,
        token: str | None,
        suggestion_id: str,
        action: str,
        message: str,
    ) -> SourceSuggestionRead | None:
        self._require_admin(token)
        principal = self._container.authenticator().resolve(token)
        decided_by = str(getattr(principal, "user_id", "admin"))
        status = "approved" if action == "approve" else "cancelled"
        row = self._store.resolve_suggestion(suggestion_id, status, message, decided_by)
        if row is None:
            return None
        # Notificación por email (pendiente de SMTP: se registra en log).
        logging.getLogger("osap.sources").info(
            "source suggestion %s -> %s for user %s: %s", suggestion_id, status, row.get("requested_by"), message
        )
        return SourceSuggestionRead(
            id=str(row["id"]),
            name=str(row["name"]),
            type=str(row["type"]),
            location=str(row["location"]),
            mapping=json.loads(str(row["mapping"])),
            requested_by=str(row["requested_by"]),
            status=str(row["status"]),
            admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
            created_at=str(row["created_at"]),
        )

    def _require_admin(self, token: str | None) -> None:
        from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

        principal = self._container.authenticator().resolve(token)
        if principal is None:
            raise UnauthenticatedError("Login required")
        if not getattr(principal, "has_role", lambda r: False)("admin"):
            raise ForbiddenError("Admin role required")

    # --- discovery ----------------------------------------------------------

    def discover_sources(self) -> list[DiscoverSource]:
        sources = [
            DiscoverSource(
                source_id=s.source_id,
                name=s.name,
                type=s.type,
                origin=s.origin,
                trust=s.trust,
                quality=s.quality,
                url=s.website,
            )
            for s in self._catalog.list()
        ]
        seen = {s.source_id for s in sources}
        for pid, name, base_url, wired in self._container.defined_providers():
            if pid in seen:
                continue
            sources.append(
                DiscoverSource(
                    source_id=pid,
                    name=name,
                    type="Provider",
                    origin=_host_of(base_url),
                    trust="Verified" if wired else "Community",
                    quality=90 if wired else 50,
                    url=base_url,
                )
            )
            seen.add(pid)
        return sources

    def statistics(self) -> SystemStatisticsResponse:
        base = self._knowledge.base()
        return SystemStatisticsResponse(
            providers=len(self._container.catalog_manager().providers()),
            searches=len(self._searches),
            jobs=len(self._jobs),
            knowledge_observations=len(base.observations),
            knowledge_facts=len(base.facts),
            knowledge_suggestions=len(base.suggestions),
        )
