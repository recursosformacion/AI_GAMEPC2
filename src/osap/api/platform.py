"""V3.1 — OSAP Platform API application layer.

Use cases exposed by the API. It calls existing Application Services (never domain
internals directly) and produces the public contract DTOs. Pure orchestration; no HTTP.
"""

import logging
import re
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.osap.api.contracts import (
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
    SystemStatisticsResponse,
    SystemVersionResponse,
    WorkInfo,
    WorkRelationships,
)
from src.osap.application.canonicalizer import Canonicalizer
from src.osap.application.jobs import DefaultJob
from src.osap.bootstrap.container import Container
from src.osap.domain.jobs import JobContext, JobTrigger
from src.osap.domain.knowledge import KnowledgeBase
from src.osap.domain.resolve_request import ResolveRequestBuilder

VERSION = "3.1"

logger = logging.getLogger("osap.api.platform")

_CANONICALIZER: Canonicalizer | None
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


def _host_of(url: str) -> str:
    """Extract the host from a provider base URL (fallback to the raw URL)."""
    try:
        return urllib.parse.urlsplit(url).netloc or url
    except Exception:
        return url


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
            tags=["Open", "MusicXML", "Community"],
            community_rating=5,
            reviews=12,
            searches=980,
            downloads=2210,
            contributions=18,
            availability=99.5,
        ),
        RepositorySource(
            source_id="cdn",
            name="OpenMusicRepository CDN",
            type="R2",
            origin="Official",
            trust="Verified",
            status="Online",
            quality=99,
            quality_label="Excellent",
            updated_at="2026-08-12 09:14 UTC",
            representations=0,
            works=0,
            composers=0,
            formats=["MusicXML", "PDF", "MIDI"],
            catalogues=[],
            duplicate_percent=0.0,
            coverage=[],
            capabilities=["Search", "Download", "Incremental Sync"],
            description="Platform object storage (Cloudflare R2) hosting score files (cdn.openmusicrepository.com).",
            license="Mixed",
            website="https://cdn.openmusicrepository.com",
            contact="",
            notes="Backend del propio OpenMusicRepository (osap-storage).",
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
        self._jobs: dict[str, JobResponse] = {}
        self._representations: dict[str, dict[str, object]] = {}
        self._job_counter = 0

    # --- search -------------------------------------------------------------

    def create_search(self, req: SearchRequest) -> tuple[str, SearchResponse]:
        search_id = uuid.uuid4().hex
        results, total = self._run_search(req)
        response = SearchResponse(
            search_id=search_id,
            results=results,
            total=total,
            page=req.page,
            per_page=req.limit,
        )
        self._searches[search_id] = response
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
            if composer in q:
                # Return the canonical composer name (not the raw query), so the composer
                # search can filter by composer alone instead of a free-text phrase.
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
                    options=["IMSLP", "OpenScore", "Local", "OpenMusicRepository"],
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

    def _run_search(self, req: SearchRequest) -> tuple[list[SearchResultItem], int]:
        builder = ResolveRequestBuilder()
        if req.query:
            builder = builder.text(req.query)
        if req.composer:
            builder = builder.composer(req.composer)
        if req.title:
            builder = builder.title(req.title)
        if req.catalogue:
            builder = builder.text(req.catalogue)
        if req.instrumentation:
            builder = builder.instrumentation(req.instrumentation)
        if req.language:
            builder = builder.language(req.language)
        request = builder.build()
        logger.info(
            "search start query=%r composer=%r title=%r catalogue=%r",
            req.query,
            req.composer,
            req.title,
            req.catalogue,
        )
        engine = self._container.work_resolution_engine()
        ranked = engine.rank(request)
        ranked_providers = sorted({c.provider_id.value for c in ranked})
        logger.info(
            "search ranked=%d providers=%s (openmusicrepository=%s)",
            len(ranked),
            ranked_providers,
            "openmusicrepository" in ranked_providers,
        )
        groups = list(self._container.work_merge_service().group(ranked))
        logger.info("search groups=%d", len(groups))
        # Strict entity filters (providers may return loose matches for free-text).
        if req.composer:
            groups = [g for g in groups if g.work.composer and req.composer.lower() in g.work.composer.lower()]
        if req.title:
            groups = [g for g in groups if g.work.title and req.title.lower() in g.work.title.lower()]
        if req.catalogue:
            groups = [
                g
                for g in groups
                if g.work.catalogue_number and req.catalogue.lower() in g.work.catalogue_number.lower()
            ]
        results: list[SearchResultItem] = []
        total = len(groups)
        start = (req.page - 1) * req.limit
        for group in groups[start : start + req.limit]:
            work = group.work
            reps = []
            for m in group.representations:
                if m is not None:
                    rep_id = f"r-{uuid.uuid4().hex[:10]}"
                    self._representations[rep_id] = {
                        "download_url": m.download_url,
                        "composer": work.composer,
                        "title": work.title,
                        "catalogue": work.catalogue_number,
                        "format": m.format.value,
                    }
                    reps.append(
                        RepresentationInfo(
                            id=rep_id,
                            provider=m.provider_id.value,
                            format=m.format.value,
                            confidence=m.confidence.value,
                            title=m.work_descriptor.title,
                        )
                    )
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
                    ),
                    representation=best,
                    representations=reps,
                    score=best.confidence,
                    evidence=[],
                    relationships=self._work_relationships(work),
                )
            )
        return results, total

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
        responses = [self._provider_response(provider) for provider in self._container.catalog_manager().providers()]
        active_ids = {r.provider_id for r in responses}
        for pid, name, _base_url, wired in self._container.defined_providers():
            if pid in active_ids or pid == "local":
                continue
            responses.append(
                ProviderResponse(provider_id=pid, name=name, available=wired, formats=[], last_sync=None)
            )
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
        return self._catalog.get(source_id)

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
