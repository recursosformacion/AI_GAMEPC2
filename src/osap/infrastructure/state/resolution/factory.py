"""Factoría del almacén de resolución (F5.8)."""

from __future__ import annotations

import logging

import pymysql

from .memory import _MemoryStore
from .mysql import _MysqlStore

_LOGGER = logging.getLogger("osap.resolution")



def build_resolution_store(
    host: str = "127.0.0.1",
    user: str = "osap2027",
    password: str = "2027osapdb",
    database: str = "osap-api",
) -> _MemoryStore:
    """Factoría: MySQL con fallback a memoria si no está disponible."""
    params = {"host": host, "user": user, "password": password, "database": database}
    try:
        store = _MysqlStore(**params)
        store._init()
        return store
    except pymysql.err.OperationalError as exc:
        _LOGGER.warning("MySQL de resolución no disponible (%s); usando almacén en memoria", exc)
        return _MemoryStore()

