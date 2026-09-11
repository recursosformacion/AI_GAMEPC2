"""Factoría del almacén operativo: MySQL con degradación a memoria."""

from __future__ import annotations

import logging

import pymysql

from .memory import MemoryStore as _MemoryStore
from .mysql import _MysqlStore

_LOGGER = logging.getLogger("osap.state")


def build_op_store(
    host: str = "127.0.0.1",
    user: str = "osap2027",
    password: str = "2027osapdb",
    database: str = "osap-api",
) -> _MemoryStore:
    """Factoría: MySQL con fallback a memoria si no está disponible."""
    params = {"host": host, "user": user, "password": password, "database": database}
    try:
        store = _MysqlStore(**params)  # __init__ ya ejecuta _init() (y _migrate()).
        return store
    except pymysql.err.OperationalError as exc:
        _LOGGER.warning("MySQL operativo no disponible (%s); usando almacén en memoria", exc)
        return _MemoryStore()
