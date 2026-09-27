"""Eventos del funnel (fase 4.2): tipos, append-only, override_id y tolerancia a fallos."""

from src.osap.api.platform.funnel import FunnelMixin
from src.osap.infrastructure.state.funnel.memory import FunnelEvent, FunnelStage, MemoryStore


def test_tipos_de_evento_y_estado() -> None:
    assert {e.value for e in FunnelEvent} == {
        "limit_reached",
        "registered",
        "membership_activated",
        "membership_lapsed",
        "promotion_applied",
        "promotion_reverted",
    }
    assert {s.value for s in FunnelStage} == {"S1", "S2", "S3", "S4"}


def test_record_event_guarda_append_only() -> None:
    store = MemoryStore()
    store.record_event(FunnelEvent.LIMIT_REACHED, stage=FunnelStage.S1, ip_address="1.2.3.4")
    store.record_event(
        FunnelEvent.PROMOTION_APPLIED,
        stage=FunnelStage.S4,
        user_id="u1",
        override_id=42,
        detail={"limit": 1000},
        day="2026-09-26",
    )
    assert store.count() == 2
    assert store.count(FunnelEvent.LIMIT_REACHED) == 1
    assert store.count(day="2026-09-26") == 1
    row = store.events[-1]
    assert row["override_id"] == 42
    assert row["detail"] == {"limit": 1000}
    assert row["day"] == "2026-09-26"


def test_es_append_only_sin_mutadores() -> None:
    store = MemoryStore()
    for banned in ("update", "delete", "remove", "edit"):
        assert not hasattr(store, banned), f"funnel_events no debe exponer {banned}()"


def test_events_for_user() -> None:
    store = MemoryStore()
    store.record_event(FunnelEvent.REGISTERED, user_id="u1", day="2026-09-27")
    store.record_event(FunnelEvent.LIMIT_REACHED, user_id="u2", day="2026-09-27")
    assert len(store.events_for_user("u1")) == 1
    assert store.events_for_user("u1", day="2026-09-26") == []


class _OkApi(FunnelMixin):
    def __init__(self) -> None:
        self._funnel_store = MemoryStore()


class _BrokenApi(FunnelMixin):
    def __init__(self) -> None:
        class _Boom:
            def record_event(self, *a: object, **k: object) -> object:
                raise RuntimeError("store caido")

        self._funnel_store = _Boom()


def test_mixin_registra_y_normaliza() -> None:
    api = _OkApi()
    api.record_funnel_event("limit_reached", stage="S1", ip_address="9.9.9.9")
    assert api._funnel_store.count(FunnelEvent.LIMIT_REACHED) == 1  # type: ignore[attr-defined]


def test_mixin_no_rompe_si_el_store_falla() -> None:
    api = _BrokenApi()
    assert api.record_funnel_event(FunnelEvent.REGISTERED, user_id="u1") == {}
    # evento inválido tampoco rompe
    assert api.record_funnel_event("no_existe") == {}
