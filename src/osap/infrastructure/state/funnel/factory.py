"""Factoría del almacén de eventos del funnel: MySQL con degradación a memoria."""

from __future__ import annotations

import logging

import pymysql

from .memory import MemoryStore as _MemoryStore
from .mysql import _MysqlStore

_LOGGER = logging.getLogger("osap.state")


def build_funnel_store(
    host: str = "127.0.0.1",
    user: str = "osap2027",
    password: str = "2027osapdb",
    database: str = "osap-api",
) -> _MemoryStore:
    params = {"host": host, "user": user, "password": password, "database": database}
    try:
        return _MysqlStore(**params)
    except pymysql.err.OperationalError as exc:
        _LOGGER.warning("MySQL de funnel no disponible (%s); usando almacén en memoria", exc)
        return _MemoryStore()
