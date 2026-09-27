"""Paso 5 (4.2): reconciliador de membresía → override donor.

Cubre: aplicar 1000 con vigencia exacta, tier≠donor → sin promoción, inactiva → retirada,
idempotencia, renovación sin duplicados, failure de support ≠ inactivo, eventos correctos,
fallo del store seguro, sin escrituras en el contador de cuota y reversibilidad.
"""

from __future__ import annotations

from datetime import datetime

from src.osap.application.reconcile_membership import (
    ReconcileMembershipUseCase,
    SupportUnavailableError,
)
from src.osap.infrastructure.state.funnel.memory import FunnelEvent
from src.osap.infrastructure.state.funnel.memory import MemoryStore as FunnelStore
from src.osap.infrastructure.state.quota.memory import MemoryStore as QuotaStore

USER = "u1"
VF = datetime(2026, 1, 1)
VU = datetime(2026, 12, 31)


class _Snap:
    def __init__(self, **kw: object) -> None:
        self.active = bool(kw.get("active", True))
        self.tier = kw.get("tier", "donor")
        self.valid_from = kw.get("valid_from", VF)
        self.valid_until = kw.get("valid_until", VU)
        self.source = kw.get("source", "stripe")


class _Source:
    def __init__(self, result: object) -> None:
        self._result = result

    def fetch(self, user_id: str) -> object:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _use_case(source: object, *, quota: object | None = None, funnel: object | None = None):
    q = quota if quota is not None else QuotaStore()
    f = funnel if funnel is not None else FunnelStore()
    return ReconcileMembershipUseCase(source=source, quota=q, funnel=f), q, f  # type: ignore[arg-type]


def _override(q: object, user_id: str = USER) -> dict[str, object] | None:
    for r in q.list_overrides():  # type: ignore[attr-defined]
        if r["user_id"] == user_id:
            return dict(r)
    return None


def test_donor_activo_aplica_override_1000_con_vigencia_exacta() -> None:
    uc, q, f = _use_case(_Source(_Snap()))
    assert uc.reconcile_user(USER) == "applied"
    ov = _override(q)
    assert ov is not None
    assert int(str(ov["downloads_per_day"])) == 1000
    assert str(ov["valid_from"])[:10] == "2026-01-01"
    assert str(ov["valid_until"])[:10] == "2026-12-31"
    assert f.count(FunnelEvent.MEMBERSHIP_ACTIVATED) == 1
    assert f.count(FunnelEvent.PROMOTION_APPLIED) == 1


def test_tier_no_donor_no_promociona() -> None:
    uc, q, f = _use_case(_Source(_Snap(tier="supporter")))
    assert uc.reconcile_user(USER) == "noop"
    assert _override(q) is None
    assert f.count() == 0


def test_inactiva_retira_override_y_emite_lapsed() -> None:
    uc, q, f = _use_case(_Source(_Snap(active=False)))
    q.set_override(USER, 1000, "2026-01-01", "2026-12-31")
    assert uc.reconcile_user(USER) == "lapsed"
    assert _override(q) is None
    assert f.count(FunnelEvent.MEMBERSHIP_LAPSED) == 1


def test_idempotencia_repetida_no_duplica() -> None:
    uc, q, f = _use_case(_Source(_Snap()))
    assert uc.reconcile_user(USER) == "applied"
    assert uc.reconcile_user(USER) == "noop"
    assert uc.reconcile_user(USER) == "noop"
    assert len(q.list_overrides()) == 1
    assert f.count(FunnelEvent.MEMBERSHIP_ACTIVATED) == 1  # no se repite
    assert f.count(FunnelEvent.PROMOTION_APPLIED) == 1


def test_renovacion_actualiza_sin_duplicar() -> None:
    source = _Source(_Snap(valid_until=datetime(2026, 12, 31)))
    uc, q, f = _use_case(source)
    assert uc.reconcile_user(USER) == "applied"
    source._result = _Snap(valid_until=datetime(2027, 12, 31))  # renovación
    assert uc.reconcile_user(USER) == "updated"  # cambio de vigencia
    ov = _override(q)
    assert ov is not None and str(ov["valid_until"])[:10] == "2027-12-31"
    assert len(q.list_overrides()) == 1  # un único override
    assert f.count(FunnelEvent.PROMOTION_APPLIED) == 2  # applied + updated


def test_support_caido_no_retira_promocion() -> None:
    uc, q, f = _use_case(_Source(SupportUnavailableError("timeout")))
    q.set_override(USER, 1000, "2026-01-01", "2026-12-31")
    assert uc.reconcile_user(USER) == "skipped"
    assert _override(q) is not None  # NO se retira
    assert f.count(FunnelEvent.MEMBERSHIP_LAPSED) == 0


def test_fallo_del_funnel_no_rompe() -> None:
    class _Broken:
        def record_event(self, *a: object, **k: object) -> object:
            raise RuntimeError("funnel caido")

    uc, q, _f = _use_case(_Source(_Snap()), funnel=_Broken())
    assert uc.reconcile_user(USER) == "applied"
    assert _override(q) is not None


def test_fallo_del_store_de_cuota_es_seguro() -> None:
    class _BrokenQuota(QuotaStore):
        def set_override(self, *a: object, **k: object) -> None:
            raise RuntimeError("cuota caida")

    uc, q, _f = _use_case(_Source(_Snap()), quota=_BrokenQuota())
    summary = uc.reconcile([USER])  # no debe lanzar
    assert summary["skipped"] == 1


def test_no_escribe_en_contador_de_cuota() -> None:
    uc, q, _f = _use_case(_Source(_Snap()))
    uc.reconcile_user(USER)
    assert q.counters == {}  # download_quota_daily intacto
    assert q.usage == []  # download_usage intacto


def test_reversibilidad_apply_verify_reconcile() -> None:
    # apply → verify → reconcile again → mismo estado (no deriva).
    uc, q, _f = _use_case(_Source(_Snap()))
    uc.reconcile_user(USER)
    first = _override(q)
    uc.reconcile_user(USER)
    assert _override(q) == first
