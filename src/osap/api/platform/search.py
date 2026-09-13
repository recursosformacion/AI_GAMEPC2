"""PlatformApi: mixin de búsqueda (F5.4)."""

import re
import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.osap.api.contracts import (
    IntentResponse,
    RepresentationInfo,
    SearchModel,
    SearchModelBlock,
    SearchModelCriteria,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    WorkInfo,
    WorkRelationships,
)
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking import RankingContext, UserPreferences
from src.osap.domain.resolve_request import ResolveRequestBuilder
from src.osap.domain.value_objects import ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

if TYPE_CHECKING:
    from src.osap.domain.work_group import WorkGroup


from src.osap.api.platform import _support as _support
from src.osap.api.platform._support import (
    _NORMALIZER,
    _PROVIDER_OPTION_LABEL,
    _PROVIDER_OPTION_ORDER,
    _STUDIO_VOICING_OPTIONS,
    _classify_collection,
    _format_for_name,
    _genre_id_for_name,
    _is_arrangement_extra,
    _provider_id_for_name,
    _search_signature,
    _studio_genre_names,
    _title_core_match,
    logger,
)

from .core import PlatformApiCore

VERSION = "3.1"



class SearchMixin(PlatformApiCore):
    def get_representation_download(self, representation_id: str) -> dict[str, object] | None:
        cached = self._representations.get(representation_id)
        if cached is not None:
            return cached
        # Fallback del índice: los ids `idx-<work>-<provider>-<format>` son deterministas
        # y permiten resolver view/download aunque el proceso se haya reiniciado.
        try:
            providers = self._container.catalog_manager().providers()
        except Exception:  # noqa: BLE001
            return None
        for provider in providers:
            pid = getattr(getattr(provider, "provider_id", None), "value", "")
            resolver = getattr(provider, "get_representation", None)
            if pid == "index" and callable(resolver):
                resolved = resolver(representation_id)
                if isinstance(resolved, dict):
                    info: dict[str, object] = {str(k): v for k, v in resolved.items()}
                    self._representations[representation_id] = info
                    return info
                return None
        return None

    # --- jobs ---------------------------------------------------------------

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
            # Una llamada = una búsqueda contada, también cuando se sirve de caché.
            self.record_search_event(cached.total)
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
                # No reducir lo ya mostrado: evita el efecto "23 → 8" cuando el resultado
                # final (o intermedio) trae menos por diferencias de agrupación/ventana.
                previous = self._searches.get(search_id)
                if previous is not None and previous.total and previous.total > total:
                    results = list(previous.results)
                    total = previous.total
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
                previous = self._searches.get(search_id)
                if previous is not None and previous.total and previous.total > total:
                    results = list(previous.results)
                    total = previous.total
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
                self.record_search_event(total)
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
        if _support._CANONICALIZER is not None:
            if composer:
                canonical = _support._CANONICALIZER.canonicalize(composer).output
                aliases.update(a for a in _support._CANONICALIZER.aliases_for(canonical) if a)
            if catalogue:
                canonical_cat = _support._CANONICALIZER.canonicalize(catalogue).output
                related = [a for a in _support._CANONICALIZER.aliases_for(canonical_cat) if a]
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

    def _studio_provider_options(self) -> list[str]:
        """Opciones del bloque "Dónde" del Estudio: SOLO los proveedores disponibles.

        La lista estática anterior marcaba fuentes caídas a las que no se podía
        conectar. Se muestran únicamente los proveedores en línea (misma fuente de
        verdad que la pantalla de proveedores). Si no hay ninguno, se mantiene la
        lista conocida para no vaciar la pantalla.
        """
        try:
            online = {r.provider_id for r in self.list_providers() if r.available}
        except Exception:  # noqa: BLE001 — no bloquear el modelo por un store inaccesible
            online = set()
        options = [
            _PROVIDER_OPTION_LABEL[pid]
            for pid in _PROVIDER_OPTION_ORDER
            if pid in online
        ]
        if options:
            return options
        return [_PROVIDER_OPTION_LABEL[pid] for pid in _PROVIDER_OPTION_ORDER]

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
                    options=self._studio_provider_options(),
                ),
                SearchModelBlock(
                    id="what_kind",
                    label="WHAT KIND",
                    kind="multi",
                    options=["MusicXML", "PDF", "MIDI"],
                ),
                SearchModelBlock(
                    id="voicing",
                    label="VOICING",
                    kind="multi",
                    options=list(_STUDIO_VOICING_OPTIONS),
                ),
                SearchModelBlock(
                    id="genre",
                    label="GENRE",
                    kind="multi",
                    options=_studio_genre_names(),
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
        # Formación vocal (voices): criterio descriptivo, NO identidad. Cada provider
        # decide si lo usa (solo CPDL lo consume hoy); el resto lo ignora.
        for voice in req.voices or []:
            builder = builder.voices(voice)
        # Género (macro-familias): se resuelve a genre_id y solo el índice local lo
        # aplica (obras OMR categorizadas); el resto de fuentes lo ignora.
        for genre_name in req.genres or []:
            genre_id = _genre_id_for_name(genre_name)
            if genre_id is not None:
                builder = builder.genre_ids(genre_id)
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

        def query_descriptor() -> WorkDescriptor:
            return WorkDescriptor(
                work_id=WorkId("web-search"),
                title=(req.title or req.query or " "),
                composer=composer_canonical or req.composer,
                catalogue_number=req.catalogue,
            )

        def build_results(
            candidates: tuple[CandidateRepresentation, ...],
        ) -> tuple[list[SearchResultItem], int]:
            # F4.C: las representaciones son evidencia -> se agrupan en obras (WorkGrouper)
            # -> la obra se puntúa (DefaultWorkRanker V2.1) -> se presentan ordenadas por
            # su score. El orden ya no es el orden accidental del rank V1.
            groups_raw = tuple(self._container.work_merge_service().group(candidates))
            ranking = self._container.work_ranker().rank(
                groups_raw,
                RankingContext(query_descriptor=query_descriptor(), user_preferences=UserPreferences()),
                self._container.work_ranking_policy(),
            )
            score_by_key: dict[str, float] = {score.work.key: score.score for score in ranking.order}
            groups: list[WorkGroup] = [score.work for score in ranking.order]
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
                        if (
                            wanted_pids
                            and rep.provider not in wanted_pids
                            # El índice devuelve candidatos con el provider REAL (omr/imslp),
                            # pero su origen es "index": si se pidió "index", hay que
                            # conservarlos (si no, index-only daba siempre 0).
                            and not ("index" in wanted_pids and m.origin == "index")
                        ):
                            continue
                        reps.append(rep)
                if not reps:
                    continue
                # Dedupe por (provider, url): el merge de grupos puede duplicar una misma
                # página/representación (p. ej. una página CPDL con varios voicings).
                seen: set[tuple[str, str]] = set()
                unique_reps: list[RepresentationInfo] = []
                for rep in reps:
                    key = (rep.provider, rep.url or "")
                    if key in seen:
                        continue
                    seen.add(key)
                    unique_reps.append(rep)
                reps = unique_reps
                best = max(reps, key=lambda r: r.confidence)
                item = SearchResultItem(
                    work=WorkInfo(
                        work_id=work.work_id.value,
                        title=work.title,
                        composer=work.composer,
                        catalogue=work.catalogue_number,
                        collection=_classify_collection(work.title),
                    ),
                    representation=best,
                    representations=reps,
                    score=round(score_by_key.get(group.key, 0.0), 3),
                    evidence=[],
                    relationships=self._work_relationships(work),
                )
                self._work_detail_cache[str(work.work_id.value)] = item.model_dump()
                results.append(item)
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

        gathered = engine.gather(request, on_progress=on_provider, on_index_partial=index_partial)
        if progress is not None:
            progress(60)
        candidates = gathered.candidates
        ranked_providers = sorted({c.provider_id.value for c in candidates})
        logger.info(
            "search candidates=%d providers=%s (openmusicrepository=%s)",
            len(candidates),
            ranked_providers,
            "openmusicrepository" in ranked_providers,
        )
        results, total = build_results(candidates)
        if progress is not None:
            progress(85)
        logger.info("search groups=%d", len(results))
        if on_partial is not None:
            on_partial(results, total)
        enriched = self._enrich_search_results(results, req.formats, req.providers)
        # total = obras que quedan tras el filtro de formatos/proveedores.
        filtered_total = len([r for r in enriched if r.representations])
        return enriched, filtered_total

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
            reps_all = self._dedupe_reps(list(current.values()))
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
            reps_all = self._dedupe_reps(list(merged.values()))
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

    def _dedupe_reps(self, reps: list[RepresentationInfo]) -> list[RepresentationInfo]:
        """Elimina representaciones duplicadas (misma fuente y mismo enlace)."""
        seen: set[tuple[str, str]] = set()
        out: list[RepresentationInfo] = []
        for rep in reps:
            key = (rep.provider, rep.url or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(rep)
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
            ranked = self._container.work_resolution_engine().gather(request).candidates
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

