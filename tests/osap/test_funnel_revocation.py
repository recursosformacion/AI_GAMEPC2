"""Paso 6 (4.2): revocación administrativa del donor + respeto por el reconciliador.

Cubre: admin autorizado, motivo obligatorio (422), revocación → override fuera + evento
`promotion_reverted` (S3/reason/periodo), idempotencia (sin override no hay evento), sin tocar
contadores/usage, fallo del funnel no deshace la revocación, 401/403, y —clave— que un
`reconcile` posterior NO resucite la promoción en el mismo periodo (sí en uno renovado).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http.context import HttpContext
from src.osap.api.http.quota import build_quota_router
from src.osap.api.platform.funnel import FunnelMixin
from src.osap.api.platform.quota import QuotaMixin
from src.osap.application.reconcile_membership import ReconcileMembershipUseCase
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError
from src.osap.infrastructure.state.funnel.memory import FunnelEvent
from src.osap.infrastructure.state.funnel.memory import MemoryStore as FunnelStore
from src.osap.infrastructure.state.quota.memory import MemoryStore as QuotaStore

ADMIN = {"Authorization": "Bearer admin"}
USER = "u1"
VF = "2026-01-01"
VU = "2026-12-31"


class _BrokenFunnel:
    def reverted_periods(self, user_id: str) -> set[str]:
        return set()

    def has_event(self, *a: object, **k: object) -> bool:
        return False

    def record_event(self, *a: object, **k: object) -> object:
        raise RuntimeError("funnel caido")


class _Api(QuotaMixin, FunnelMixin):
    def __init__(self, *, funnel: object | None = None) -> None:
        self._quota_store = QuotaStore()
        self._funnel_store = funnel if funnel is not None else FunnelStore()

    def _require_admin(self, token: str | None) -> None:
        if not token:
            raise UnauthenticatedError("login required")
        if token != "Bearer admin":
            raise ForbiddenError("admin required")


def _client(api: _Api) -> TestClient:
    app = FastAPI()
    app.include_router(build_quota_router(HttpContext(api=api, container=object())))  # type: ignore[arg-type]
    return TestClient(app)


def _revoke(client: TestClient, *, reason: str = "fraude", headers: dict[str, str] = ADMIN):
    return client.post(
        f"/api/v1/admin/quota/overrides/{USER}/revoke", json={"reason": reason}, headers=headers
    )


def _override(api: _Api):
    return api._quota_store.list_overrides()


def test_admin_requerido() -> None:
    api = _Api()
    api._quota_store.set_override(USER, 1000, VF, VU)
    assert _revoke(_client(api), headers={}).status_code == 401
    assert _revoke(_client(api), headers={"Authorization": "Bearer user"}).status_code == 403


def test_motivo_obligatorio_422() -> None:
    api = _Api()
    api._quota_store.set_override(USER, 1000, VF, VU)
    client = _client(api)
    assert client.post(
        f"/api/v1/admin/quota/overrides/{USER}/revoke", json={}, headers=ADMIN
    ).status_code == 422
    assert _revoke(client, reason="   ").status_code == 422


def test_revocacion_valida_elimina_override_y_emite_evento() -> None:
    api = _Api()
    api._quota_store.set_override(USER, 1000, VF, VU)
    resp = _revoke(_client(api), reason="fraude")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["revoked"] is True
    assert _override(api) == []  # override fuera

    funnel = api._funnel_store
    assert funnel.count(FunnelEvent.PROMOTION_REVERTED) == 1
    ev = funnel.events[0]
    assert ev["stage"] == "S3"
    assert ev["user_id"] == USER
    assert ev["detail"]["reason"] == "fraude"
    assert ev["detail"]["valid_from"] == VF  # periodo revocado
    # No toca contadores ni usage
    assert api._quota_store.counters == {}
    assert api._quota_store.usage == []


def test_sin_override_es_noop_sin_evento() -> None:
    api = _Api()
    body = _revoke(_client(api)).json()["data"]
    assert body["revoked"] is False
    assert api._funnel_store.count() == 0


def test_revocacion_repetida_idempotente() -> None:
    api = _Api()
    api._quota_store.set_override(USER, 1000, VF, VU)
    client = _client(api)
    assert _revoke(client).json()["data"]["revoked"] is True
    assert _revoke(client).json()["data"]["revoked"] is False
    assert api._funnel_store.count(FunnelEvent.PROMOTION_REVERTED) == 1


def test_fallo_del_funnel_no_desahce_la_revocacion() -> None:
    api = _Api(funnel=_BrokenFunnel())
    api._quota_store.set_override(USER, 1000, VF, VU)
    assert _revoke(_client(api)).status_code == 200
    assert _override(api) == []  # la revocación funcional se mantiene


# --- interacción con el reconciliador ----------------------------------------


class _Snap:
    def __init__(self, *, valid_from: str) -> None:
        self.active = True
        self.tier = "donor"
        self.valid_from = valid_from
        self.valid_until = "2026-12-31"
        self.source = "stripe"


class _Source:
    def __init__(self, valid_from: str) -> None:
        self._vf = valid_from

    def fetch(self, user_id: str) -> object:
        return _Snap(valid_from=self._vf)


def _reconciler(api: _Api, valid_from: str) -> ReconcileMembershipUseCase:
    return ReconcileMembershipUseCase(
        source=_Source(valid_from), quota=api._quota_store, funnel=api._funnel_store
    )


def test_reconcile_no_resucita_promocion_revocada() -> None:
    api = _Api()
    api._quota_store.set_override(USER, 1000, VF, VU)
    _revoke(_client(api))  # revocación en el periodo VF
    # support sigue diciendo activa, mismo periodo → NO se promociona de nuevo
    assert _reconciler(api, VF).reconcile_user(USER) == "revoked"
    assert _override(api) == []
    assert api._funnel_store.count(FunnelEvent.PROMOTION_APPLIED) == 0


def test_reconcile_promociona_en_periodo_renovado() -> None:
    api = _Api()
    api._quota_store.set_override(USER, 1000, VF, VU)
    _revoke(_client(api))
    # membresía renovada (nuevo valid_from) → es un periodo nuevo: sí se promociona
    assert _reconciler(api, "2027-01-01").reconcile_user(USER) == "applied"
    assert len(_override(api)) == 1
