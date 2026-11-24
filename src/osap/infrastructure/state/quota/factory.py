"""Factoría del almacén de cuotas: MySQL con degradación a memoria."""

from __future__ import annotations

import logging

import pymysql

from .memory import MemoryStore as _MemoryStore
from .mysql import _MysqlStore

_LOGGER = logging.getLogger("osap.state")


def build_quota_store(
    host: str | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    port: int = 3306,
    read_only: bool = False,
) -> _MemoryStore:
    """Factoría: MySQL con fallback a memoria si no está disponible."""
    if host is None or user is None or password is None or database is None:
        _LOGGER.info("Configuración MySQL incompleta; usando almacén en memoria")
        return _MemoryStore()
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
