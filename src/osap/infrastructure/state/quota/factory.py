"""Factoría del almacén de cuotas: MySQL con degradación a memoria."""

from __future__ import annotations

import logging

import pymysql

from .memory import MemoryStore as _MemoryStore
from .mysql import _MysqlStore

_LOGGER = logging.getLogger("osap.state")


def build_quota_store(
    host: str = "127.0.0.1",
    user: str = "osap2027",
    password: str = "2027osapdb",
    database: str = "osap-api",
    port: int = 3306,
    read_only: bool = False,
) -> _MemoryStore:
    """Factoría: MySQL con fallback a memoria si no está disponible."""
    try:
        return _MysqlStore(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            read_only=read_only,
        )
    except pymysql.err.OperationalError as exc:
        _LOGGER.warning("MySQL de cuotas no disponible (%s); usando almacén en memoria", exc)
        return _MemoryStore()
