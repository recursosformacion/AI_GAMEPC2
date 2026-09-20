"""Roles de persona en el modelo nuevo de osap-storage (`persons` + `works_person_roles`).

osap-storage publica los roles con id numérico (tabla `roles`) y la API los pide por nombre
(`GET /api/v1/persons?role=composer,arranger`). Aquí se centraliza el mapeo para no
repartir "1 = compositor" por el código.

Fuente: `osap-storage.roles` (1..15). Debe mantenerse estable; si storage añade roles, se
amplía aquí (y con test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# nombre de API → id en `osap-storage.roles`
ROLE_IDS: dict[str, int] = {
    "composer": 1,
    "librettist": 2,
    "arranger": 3,
    "orchestrator": 4,
    "transcriber": 5,
    "editor": 6,
    "completer": 7,
    "conductor": 8,
    "choir_conductor": 9,
    "performer": 10,
    "kapellmeister": 11,
    "vocal_coach": 12,
    "dedicatee": 13,
    "patron": 14,
    "inspiration": 15,
}

# id → nombre de API
ROLE_NAMES: dict[int, str] = {role_id: name for name, role_id in ROLE_IDS.items()}

DEFAULT_ROLE = "composer"


def parse_roles(value: str | Iterable[str] | None, *, default: str = DEFAULT_ROLE) -> tuple[str, ...]:
    """Normaliza `role=composer,arranger` (o lista) a nombres válidos y sin duplicados.

    - `None`/vacío → `(default,)` (compatibilidad: sin rol se asume compositor, como `/composers`).
    - Ignora espacios y duplicados.
    - Lanza `ValueError` con los roles desconocidos (mejor 400 que silencio).
    """
    if value is None:
        return (default,)
    raw = value.split(",") if isinstance(value, str) else list(value)
    names: list[str] = []
    unknown: list[str] = []
    for item in raw:
        name = str(item).strip().lower()
        if not name:
            continue
        if name not in ROLE_IDS:
            unknown.append(name)
            continue
        if name not in names:
            names.append(name)
    if unknown:
        raise ValueError(f"rol desconocido: {', '.join(sorted(set(unknown)))}")
    return tuple(names) if names else (default,)


def role_ids(roles: Iterable[str]) -> tuple[int, ...]:
    """Nombres de rol → ids de `osap-storage.roles` (ignora desconocidos)."""
    return tuple(ROLE_IDS[name] for name in roles if name in ROLE_IDS)


def role_names(ids: Iterable[object]) -> list[str]:
    """Ids de rol (int o str) → nombres de API, ignorando los que no existen."""
    names: list[str] = []
    for value in ids:
        text = "" if value is None else str(value)
        if not text.isdigit():
            continue
        name = ROLE_NAMES.get(int(text))
        if name and name not in names:
            names.append(name)
    return names


def _role_id_list(ids: object) -> list[int]:
    if not isinstance(ids, list):
        return []
    return [int(str(v)) for v in ids if str(v).isdigit()]


def person_has_role(person: dict[str, object], role: str) -> bool:
    """True si el payload de una persona incluye el rol (por nombre o por id)."""
    roles = person.get("roles")
    if isinstance(roles, list) and role in [str(r).lower() for r in roles]:
        return True
    return ROLE_IDS.get(role) in _role_id_list(person.get("role_ids"))
