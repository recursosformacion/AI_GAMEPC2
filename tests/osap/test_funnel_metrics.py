"""Paso 7 (4.2): métricas del funnel derivadas (solo lectura) de events + downloads.

Cubre: dataset conocido exacto, DISTINCT de usuarios (reintentos/renovaciones no inflan),
descargas anónimas vs registradas, `promotion_reverted` separada de `membership_lapsed`,
periodo vacío, límites de fechas, funnel sin datos y —sobre todo— que calcular no escribe.
"""

from __future__ import annotations

from src.osap.application.funnel_metrics import FunnelMetricsUseCase
from src.osap.infrastructure.state.funnel.memory import MemoryStore as FunnelStore
from src.osap.infrastructure.state.quota.memory import MemoryStore as QuotaStore

FROM, TO = "2026-09-01", "2026-09-30"


def _seed() -> tuple[FunnelStore, QuotaStore]:
    f = FunnelStore()
    # S1: 3 eventos anónimos (sin user_id), 2 días distintos.
    f.record_event("limit_reached", stage="S1", ip_address="1.1.1.1", day="2026-09-10")
    f.record_event("limit_reached", stage="S1", ip_address="1.1.1.2", day="2026-09-10")
    f.record_event("limit_reached", stage="S1", ip_address="1.1.1.3", day="2026-09-11")
    # S1→S2: u1 registra dos veces (reintento) → 2 eventos, 1 usuario.
    f.record_event("registered", stage="S2", user_id="u1", day="2026-09-11")
    f.record_event("registered", stage="S2", user_id="u1", day="2026-09-11")
    f.record_event("registered", stage="S2", user_id="u2", day="2026-09-15")
    # S3: u1 alcanza el límite registrado.
    f.record_event("limit_reached", stage="S3", user_id="u1", day="2026-09-12")
    # S3→S4: u1 activa; promotion_applied x2 (apply + renovación) → 2 eventos, 1 usuario.
    f.record_event("membership_activated", stage="S4", user_id="u1", day="2026-09-12")
    f.record_event("promotion_applied", stage="S4", user_id="u1", day="2026-09-12")
    f.record_event("promotion_applied", stage="S4", user_id="u1", day="2026-09-20")
    # Caducidad (u1) y revocación manual (u3): eventos distintos.
    f.record_event("membership_lapsed", stage="S2", user_id="u1", day="2026-09-25")
    f.record_event("promotion_reverted", stage="S3", user_id="u3", day="2026-09-26",
                   detail={"reason": "x", "valid_from": "2026-09-01"})

    q = QuotaStore()
    # download_usage directo (no interesa el contador aquí): 2 anónimas + 3 registradas.
    for uid, ip in ((None, "1.1.1.1"), (None, "1.1.1.2")):
        q.usage.append({"day": "2026-09-10", "user_id": uid, "ip_address": ip,
                        "provider": "omr", "format": "musicxml", "work_id": "w1", "counts_against_plan": 1})
    for _ in range(3):
        q.usage.append({"day": "2026-09-12", "user_id": "u1", "ip_address": "9.9.9.9",
                        "provider": "omr", "format": "musicxml", "work_id": "w1", "counts_against_plan": 1})
    return f, q


def _metrics(f: FunnelStore, q: QuotaStore, frm: str = FROM, to: str = TO) -> dict[str, object]:
    return FunnelMetricsUseCase(funnel=f, quota=q).metrics(frm, to)


def test_dataset_conocido_eventos_y_usuarios() -> None:
    f, q = _seed()
    m = _metrics(f, q)
    ev = m["events"]
    us = m["users"]
    assert ev["anon_limit_reached"] == 3
    assert ev["registered"] == 3  # 3 operaciones (u1 dos veces)
    assert us["registered"] == 2  # 2 usuarios únicos (u1, u2)
    assert ev["user_limit_reached"] == 1
    assert us["user_limit_reached"] == 1
    assert ev["membership_activated"] == 1 and us["membership_activated"] == 1


def test_renovaciones_no_inflan_usuarios_unicos() -> None:
    f, q = _seed()
    m = _metrics(f, q)
    assert m["events"]["promotion_applied"] == 2  # apply + renovación
    assert m["users"]["promotion_applied"] == 1  # un único usuario


def test_reverted_y_lapsed_separadas() -> None:
    f, q = _seed()
    ev = _metrics(f, q)["events"]
    assert ev["membership_lapsed"] == 1
    assert ev["promotion_reverted"] == 1


def test_descargas_por_tipo() -> None:
    f, q = _seed()
    d = _metrics(f, q)["downloads"]
    assert d["total"] == 5
    assert d["anonymous"] == 2
    assert d["registered"] == 3


def test_conversiones_usan_usuarios_unicos() -> None:
    f, q = _seed()
    c = _metrics(f, q)["conversions"]
    assert c["anon_to_user"] == 2
    assert c["user_to_donor"] == 1


def test_periodo_vacio() -> None:
    f, q = _seed()
    m = _metrics(f, q, "2026-01-01", "2026-01-31")
    assert m["events"]["registered"] == 0
    assert m["downloads"]["total"] == 0
    assert m["conversions"]["anon_to_user"] == 0


def test_limites_de_fechas_incluyen_bordes() -> None:
    f, q = _seed()
    assert _metrics(f, q, "2026-09-10", "2026-09-10")["events"]["anon_limit_reached"] == 2
    assert _metrics(f, q, "2026-09-11", "2026-09-11")["events"]["anon_limit_reached"] == 1
    assert _metrics(f, q, "2026-09-01", "2026-09-09")["events"]["registered"] == 0


def test_funnel_sin_datos() -> None:
    m = _metrics(FunnelStore(), QuotaStore())
    assert m["events"]["registered"] == 0
    assert m["users"]["registered"] == 0
    assert m["downloads"]["total"] == 0


def test_metricas_no_escriben() -> None:
    f, q = _seed()
    f_before = list(f.events)
    q_usage_before = list(q.usage)
    q_counters_before = dict(q.counters)
    _metrics(f, q)
    assert f.events == f_before  # funnel intacto
    assert q.usage == q_usage_before  # download_usage intacto
    assert q.counters == q_counters_before  # download_quota_daily intacto
