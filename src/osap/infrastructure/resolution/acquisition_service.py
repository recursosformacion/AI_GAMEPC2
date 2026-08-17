"""Worker de adquisición de ResolutionSession (FASE 2).

Cada llamada a `process_step` ejecuta una unidad pequeña de trabajo: adquiere una página
de un proveedor, la persiste de forma idempotente y actualiza el progreso. No mantiene
estado importante solo en memoria: todo lo reanudable vive en OpStore
(`provider_results` + `resolution_sessions`).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from src.osap.infrastructure.resolution.acquisition_plan import AcquisitionPlan, build_acquisition_plan
from src.osap.infrastructure.resolution.provider_acquirer import IProviderAcquirer, provider_works_to_json
from src.osap.infrastructure.resolution.universe_matching import IUniverseMatcher, rebuild_universe

if TYPE_CHECKING:
    from src.osap.infrastructure.state.resolution_store import _MemoryStore

_LOGGER = logging.getLogger("osap.resolution")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class AcquisitionService:
    def __init__(
        self,
        store: _MemoryStore,
        acquirers: dict[str, IProviderAcquirer],
        matcher: IUniverseMatcher | None = None,
    ) -> None:
        self._store = store
        self._acquirers = acquirers
        self._matcher = matcher

    # --- plan ----------------------------------------------------------------

    def _plan_for(self, row: dict[str, object]) -> AcquisitionPlan:
        providers = json.loads(str(row.get("providers_json") or "[]"))
        policy = json.loads(str(row.get("policy_json") or "{}"))
        return build_acquisition_plan(providers, policy, self._acquirers)

    def _query_for(self, row: dict[str, object]) -> str:
        query_info = json.loads(str(row.get("query_json") or "{}"))
        return str(query_info.get("query") or "")

    # --- entrada -------------------------------------------------------------

    def next_session_id(self) -> str | None:
        rows = self._store.list_acquiring_sessions()
        return str(rows[0]["session_id"]) if rows else None

    # --- paso de trabajo -----------------------------------------------------

    def process_step(self, session_id: str) -> str:
        """Ejecuta una unidad de trabajo (una página) y devuelve el estado resultante."""
        row = self._store.get_session(session_id)
        if row is None:
            return "failed"
        if row.get("status") != "acquiring":
            return str(row["status"])

        now = datetime.now(UTC)
        if _is_expired(row, now):
            return self._expire(session_id)

        plan = self._plan_for(row)
        progress = json.loads(str(row.get("progress_json") or "{}"))
        provider = self._next_provider(session_id, plan, progress, row, now)
        if provider is not None:
            self._acquire_one(session_id, provider, plan, progress, row)
        if self._matcher is not None:
            self._run_provisional_matching(session_id)
        return self._finish(session_id, plan, progress, row, datetime.now(UTC))

    def recompute_items(self, session_id: str, stage: str = "provisional") -> int:
        """Reconstruye el universo y re-resuelve los items (sin llamar a proveedores)."""
        if self._matcher is None:
            return 0
        universe = rebuild_universe(self._store, session_id)
        items = self._matcher.match(universe)
        return self._store.replace_items(session_id, items, stage)

    def _run_provisional_matching(self, session_id: str) -> None:
        self.recompute_items(session_id, "provisional")

    def run_until_terminal(self, session_id: str, max_steps: int = 1000) -> str:
        """Procesa pasos hasta alcanzar un estado terminal (para pruebas / worker)."""
        status = "acquiring"
        steps = 0
        while status == "acquiring" and steps < max_steps:
            status = self.process_step(session_id)
            steps += 1
        return status

    # --- selección de proveedor ----------------------------------------------

    def _next_provider(
        self,
        session_id: str,
        plan: AcquisitionPlan,
        progress: dict[str, object],
        row: dict[str, object],
        now: datetime,
    ) -> str | None:
        if _duration_exceeded(row, now, plan.max_duration_s):
            return None
        for provider in plan.providers:
            if self._provider_has_work(session_id, provider, plan, progress):
                return provider
        return None

    def _provider_has_work(
        self,
        session_id: str,
        provider: str,
        plan: AcquisitionPlan,
        progress: dict[str, object],
    ) -> bool:
        stats = _provider_stats(progress, provider)
        if int(cast("int", stats.get("pages") or 0)) >= plan.max_pages_per_provider:
            return False
        if int(cast("int", stats.get("works") or 0)) >= plan.max_results_to_acquire:
            return False
        last = self._store.last_provider_result(session_id, provider)
        if last is None:
            return True
        status = str(last.get("status"))
        if status == "end_of_provider":
            return False
        if status == "fetched":
            return bool(last.get("next_cursor"))
        if status == "recoverable_error":
            return int(cast("int", stats.get("retries") or 0)) < plan.max_recoverable_retries
        return False

    # --- adquisición de una página -------------------------------------------

    def _acquire_one(
        self,
        session_id: str,
        provider: str,
        plan: AcquisitionPlan,
        progress: dict[str, object],
        row: dict[str, object],
    ) -> None:
        cursor = self._cursor_for(session_id, provider, plan)
        acquirer = self._acquirers.get(provider)
        kind = plan.pagination_kind(provider)
        now = _now()
        if acquirer is None:
            self._store.add_provider_result(
                _rid(), session_id, provider, kind, cursor, None, "recoverable_error", "[]", "{}", now
            )
            _bump_provider(progress, provider, pages=1, works=0, retries=1)
            self._store.set_progress(session_id, json.dumps(progress))
            return

        page = acquirer.acquire_page(provider, cursor, self._query_for(row))
        if page.error:
            self._store.add_provider_result(
                _rid(), session_id, provider, kind, cursor, cursor, "recoverable_error", "[]", "{}", now
            )
            _bump_provider(progress, provider, pages=1, works=0, retries=1)
            self._store.set_progress(session_id, json.dumps(progress))
            return

        status = "end_of_provider" if page.end_of_provider else "fetched"
        self._store.add_provider_result(
            _rid(),
            session_id,
            provider,
            kind,
            cursor,
            page.next_cursor,
            status,
            provider_works_to_json(page.works),
            "{}",
            now,
        )
        _bump_provider(progress, provider, pages=1, works=len(page.works))
        self._store.set_progress(session_id, json.dumps(progress))

    def _cursor_for(self, session_id: str, provider: str, plan: AcquisitionPlan) -> str:
        last = self._store.last_provider_result(session_id, provider)
        if last is not None and last.get("next_cursor"):
            return str(last["next_cursor"])
        if last is not None and last.get("status") == "recoverable_error":
            return str(last["cursor_value"])
        return plan.initial_cursor(provider)

    # --- fin -----------------------------------------------------------------

    def _finish(
        self,
        session_id: str,
        plan: AcquisitionPlan,
        progress: dict[str, object],
        row: dict[str, object],
        now: datetime,
    ) -> str:
        if _is_expired(row, now):
            return self._expire(session_id)
        limit_hit = _duration_exceeded(row, now, plan.max_duration_s)
        abandoned = False
        for provider in plan.providers:
            if self._provider_has_work(session_id, provider, plan, progress):
                return "acquiring"
            stats = _provider_stats(progress, provider)
            if int(cast("int", stats.get("pages") or 0)) >= plan.max_pages_per_provider:
                limit_hit = True
            if int(cast("int", stats.get("works") or 0)) >= plan.max_results_to_acquire:
                limit_hit = True
            last = self._store.last_provider_result(session_id, provider)
            if last is not None and str(last.get("status")) == "recoverable_error":
                abandoned = True
        final = "partial" if (limit_hit or abandoned) else "complete"
        if self._matcher is not None and final in ("complete", "partial"):
            # Resolución definitiva sobre el universo completo disponible.
            self.recompute_items(session_id, "definitive")
        self._store.update_status(session_id, final)
        return final

    def _expire(self, session_id: str) -> str:
        """TTL: la sesión deja de ser recuperable y se limpian sus datos hijos."""
        self._store.update_status(session_id, "expired")
        self._store.delete_session_data(session_id)
        return "expired"


def _bump_provider(
    progress: dict[str, object], provider: str, pages: int, works: int, retries: int = 0
) -> None:
    providers_raw = progress.get("providers")
    providers: dict[Any, Any] = providers_raw if isinstance(providers_raw, dict) else {}
    stats_raw = providers.get(provider)
    stats: dict[Any, Any] = stats_raw if isinstance(stats_raw, dict) else {}
    stats["pages"] = int(stats.get("pages") or 0) + pages
    stats["works"] = int(stats.get("works") or 0) + works
    stats["retries"] = int(stats.get("retries") or 0) + retries
    providers[provider] = stats
    progress["providers"] = providers
    progress["acquired_pages"] = int(cast("int", progress.get("acquired_pages") or 0)) + pages
    progress["acquired_works"] = int(cast("int", progress.get("acquired_works") or 0)) + works


def _provider_stats(progress: dict[str, object], provider: str) -> dict[str, object]:
    providers = progress.get("providers")
    if isinstance(providers, dict):
        stats = providers.get(provider)
        if isinstance(stats, dict):
            return stats
    return {}


def _is_expired(row: dict[str, object], now: datetime) -> bool:
    expires = str(row.get("expires_at") or "")
    try:
        return now >= datetime.fromisoformat(expires)
    except ValueError:
        return False


def _duration_exceeded(row: dict[str, object], now: datetime, max_duration_s: int) -> bool:
    created = str(row.get("created_at") or "")
    try:
        elapsed = (now - datetime.fromisoformat(created)).total_seconds()
    except ValueError:
        return False
    return elapsed >= max_duration_s


def _rid() -> str:
    return f"pr_{uuid.uuid4().hex}"
