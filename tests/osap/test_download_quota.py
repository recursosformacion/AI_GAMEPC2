"""Cuotas de descarga OMR: límites por plan, override con caducidad y consumo atómico."""

from src.osap.infrastructure.state.quota.memory import MemoryStore, QuotaDecision


def _consume(store: MemoryStore, **over: object) -> QuotaDecision:
    args: dict[str, object] = {
        "day": "2026-09-26",
        "user_id": None,
        "ip": "1.2.3.4",
        "is_admin": False,
        "work_id": "w1",
        "resource_id": 10,
        "provider": "omr",
        "fmt": "musicxml",
    }
    args.update(over)
    return store.consume(**args)  # type: ignore[arg-type]


def test_visitante_limite_10_por_ip() -> None:
    store = MemoryStore()
    for _ in range(10):
        assert _consume(store).allowed is True
    denied = _consume(store)
    assert denied.allowed is False
    assert denied.limit == 10
    assert denied.used == 10
    # Otra IP no se ve afectada.
    assert _consume(store, ip="9.9.9.9").allowed is True


def test_registrado_limite_100_por_usuario_no_por_ip() -> None:
    store = MemoryStore()
    for _ in range(100):
        assert _consume(store, user_id="u1", ip="1.1.1.1").allowed is True
    assert _consume(store, user_id="u1", ip="2.2.2.2").allowed is False  # la IP no cambia su cuota
    assert _consume(store, user_id="u2", ip="1.1.1.1").allowed is True


def test_override_con_caducidad() -> None:
    store = MemoryStore()
    store.set_override("u1", 2, "2026-09-01", "2026-09-30")
    assert _consume(store, user_id="u1", day="2026-09-26").allowed is True
    assert _consume(store, user_id="u1", day="2026-09-26").allowed is True
    assert _consume(store, user_id="u1", day="2026-09-26").allowed is False
    # Fuera de la ventana, vuelve al plan (100).
    assert _consume(store, user_id="u1", day="2026-10-01").allowed is True


def test_override_cero_bloquea() -> None:
    store = MemoryStore()
    store.set_override("u1", 0, None, None)
    assert _consume(store, user_id="u1").allowed is False


def test_admin_ilimitado_salvo_override() -> None:
    store = MemoryStore()
    for _ in range(50):
        assert _consume(store, user_id="admin1", is_admin=True).allowed is True
    store.set_override("admin1", 1, None, None)
    assert _consume(store, user_id="admin1", is_admin=True).allowed is True
    assert _consume(store, user_id="admin1", is_admin=True).allowed is False


def test_plan_donante_preparado() -> None:
    store = MemoryStore()
    assert store.plan_limit("donor") == 1000
    store.set_plan("donor", 5)
    assert store.plan_limit("donor") == 5
