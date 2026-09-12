"""PlatformApi: mixin de resolución/sesiones (F5.4)."""

import json
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import src.osap.api.platform as _platform_module
from src.osap.api.contracts import (
    RepresentationInput,
    RepresentationSelectionRead,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform._support import (
    _progress_flat,
    _selection_payload,
    _UnreadableScoreError,
)
from src.osap.api.platform.core import PlatformApiCore
from src.osap.application.representation_selector import (
    RepresentationCandidate,
)
from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.provider_acquirer import CatalogAcquirer, IProviderAcquirer
from src.osap.infrastructure.resolution.session_universe_resolver import SessionUniverseResolver

VERSION = "3.1"

# Proveedores que sirven ficheros directamente (no páginas de catálogo).
_FILE_PROVIDERS = {
    "omr",
    "local",
    "osap-storage",
    "openscore",
    "mutopia",
    "hymnary",
    "openmusicrepository",
}
_FILE_URL_SUFFIXES = (
    ".pdf",
    ".mxl",
    ".xml",
    ".musicxml",
    ".mid",
    ".midi",
    ".mei",
    ".krn",
    ".zip",
    ".ly",
)


def _is_file_candidate(r: RepresentationInput) -> bool:
    """Solo candidatas que son ficheros descargables reales.

    IMSLP publica páginas wiki y MusicBrainz páginas de obra: intentar descargarlas
    produce falsos "descarga fallida" y contamina la selección.
    """
    url = str(getattr(r, "url", "") or "")
    if not url.startswith(("http://", "https://")):
        return False
    provider = str(getattr(r, "provider", "") or "").lower()
    if provider in _FILE_PROVIDERS:
        return True
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(_FILE_URL_SUFFIXES) or "/download" in path









class ResolutionMixin(PlatformApiCore):
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
        self._acquisition = AcquisitionService(self._resolution_store, acquirers, SessionUniverseResolver())

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
        return AcquisitionService(self._resolution_store, acquirers, SessionUniverseResolver())

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
                            title=str(work.get("title") or "") or None,
                        )
                    )
        return tuple(out)

    def select_best_representation(
        self,
        work_id: str,
        representations: list[RepresentationInput],
    ) -> RepresentationSelectionRead:
        """Selecciona la mejor representación ENTRE las ya conocidas de la Work.

        No adquiere ni descubre: recibe la lista conocida (la misma que alimenta la
        UI), filtra las utilizables, valida cada candidata con el selector real y
        persiste la selección POR WORK (`work_selections`).
        """
        known = list(representations)
        usable = [r for r in known if _is_file_candidate(r)]
        if not known:
            return RepresentationSelectionRead(
                work_id=work_id,
                representations_known=0,
                candidates_usable=0,
                status="none_known",
                message="No hay representaciones conocidas para esta obra.",
            )
        if not usable:
            return RepresentationSelectionRead(
                work_id=work_id,
                representations_known=len(known),
                candidates_usable=0,
                status="none_usable",
                message="No hay una representación utilizable entre las representaciones conocidas.",
            )
        from src.osap.application.representation_selector import (
            BestRepresentationSelector,
            RepresentationCandidate,
        )

        candidates = tuple(
            RepresentationCandidate(
                provider=r.provider,
                format=r.format,
                url=str(r.url),
                source_id=r.id or f"{work_id}-{r.provider}-{r.format}",
                title=r.title,
            )
            for r in usable
        )
        selected = BestRepresentationSelector().select(candidates)
        if selected.candidate is None:
            detail = "; ".join(selected.errors) if selected.errors else selected.reason
            return RepresentationSelectionRead(
                work_id=work_id,
                representations_known=len(known),
                candidates_usable=len(candidates),
                status="none_usable",
                message="Ninguna de las representaciones conocidas superó la validación.",
                errors=[detail],
            )
        quality_score: float | None = None
        report_overall = getattr(selected.report, "overall", None)
        if callable(report_overall):
            try:
                quality_score = float(report_overall())
            except Exception:  # noqa: BLE001
                quality_score = None
        snapshot: dict[str, object] = {
            "provider": selected.candidate.provider,
            "format": selected.candidate.format,
            "url": selected.candidate.url,
            "source_id": selected.candidate.source_id,
            "title": selected.candidate.title or "",
            "quality_level": selected.quality_level.value,
            "quality_score": quality_score,
            "reason": selected.reason or "",
        }
        self._store.set_work_selection(work_id, json.dumps(snapshot, ensure_ascii=False))
        return RepresentationSelectionRead(
            work_id=work_id,
            representations_known=len(known),
            candidates_usable=len(candidates),
            status="selected",
            message="Representación seleccionada.",
            selected=snapshot,
            errors=list(selected.errors),
        )

    def get_work_selection(self, work_id: str) -> RepresentationSelectionRead | None:
        row = self._store.get_work_selection(work_id)
        if row is None:
            return None
        try:
            selected = json.loads(str(row.get("selection_json") or "{}"))
        except ValueError:
            selected = {}
        return RepresentationSelectionRead(
            work_id=work_id,
            representations_known=1,
            candidates_usable=1,
            status="selected",
            message="Representación seleccionada.",
            selected=selected if isinstance(selected, dict) else {},
        )

    def score_contract_for_session(
        self, session_id: str
    ) -> tuple[int, str, str, dict[str, object] | None]:
        """Produce un `ScoreContract` (JSON) para una sesión ya resuelta.

        La sesión ya identificó la obra y seleccionó la mejor representación
        (`selection_json`). El productor reutiliza esa selección: descarga la URL
        elegida y la revalida con el mismo `BasicValidator`/MusicXmlValidator del
        pipeline (no hay parser ni validador paralelo; el `Score` no se persiste, por
        eso se revalida la representación ya elegida, sin volver a seleccionar).

        Devuelve: (status_code, error_code, mensaje, payload). En éxito el payload es
        `{"score_contract": {...}}` (más identidad de la obra cuando se puede derivar).
        """
        row = self._resolution_store.get_session(session_id)
        if row is None:
            return 404, "SESSION_NOT_FOUND", "Sesión no encontrada", None
        status = str(row.get("status") or "")
        selection_raw = row.get("selection_json")
        if status not in ("complete", "partial") or not selection_raw:
            return (
                409,
                "NO_SELECTION",
                "La sesión no tiene una representación seleccionada",
                None,
            )
        try:
            selection = json.loads(str(selection_raw))
        except ValueError:
            return 422, "INVALID_SELECTION", "Selección de representación inválida", None
        url = str((selection or {}).get("url") or "")
        if not url.startswith(("http://", "https://")):
            return (
                422,
                "INVALID_SELECTION",
                "La representación seleccionada no tiene URL descargable",
                None,
            )
        content = _platform_module._fetch_url_bytes(url)
        if content is None:
            return 502, "FETCH_FAILED", "No se pudo obtener la representación", None
        identity = self._match_work_identity(session_id, url)
        try:
            contract = _platform_module._validate_to_contract(content, identity)
        except _UnreadableScoreError:
            return (
                422,
                "INVALID_REPRESENTATION",
                "La representación no es una partitura válida",
                None,
            )
        except Exception:  # noqa: BLE001
            return 500, "INTERNAL", "No se pudo generar el contrato", None
        payload: dict[str, object] = {"score_contract": contract}
        if identity is not None:
            payload["work"] = identity
        return 200, "", "", payload

    def _match_work_identity(self, session_id: str, url: str) -> dict[str, object] | None:
        """Localiza en los resultados de la sesión la obra dueña de la URL elegida."""
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
                    if str(links.get("download") or "") != url:
                        continue
                    identity = work.get("identity")
                    if isinstance(identity, dict):
                        return {
                            "title": str(identity.get("title") or "") or None,
                            "composer": str(identity.get("composer") or "") or None,
                            "provider": str(work.get("provider") or "") or None,
                        }
        return None

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

