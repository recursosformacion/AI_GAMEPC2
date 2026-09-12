"""Recorder de analítica no bloqueante (buffer en memoria + flush por lote).

La analítica **nunca** debe añadir latencia ni tumbar una petición: los eventos se acumulan
en memoria (agregando claves idénticas) y un hilo daemon los vuelca al store cada
`flush_interval` segundos o al alcanzar `max_buffer` eventos. Cualquier error del store se
registra y se descarta: perder un contador es preferible a romper una descarga.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from .memory import ANON_USER, today

if TYPE_CHECKING:
    from collections.abc import Callable
from .memory import MemoryStore as _MemoryStore

_LOGGER = logging.getLogger("osap.analytics")


class AnalyticsRecorder:
    """Buffer de eventos de uso con flush periódico y tolerante a fallos."""

    def __init__(
        self,
        store: _MemoryStore,
        flush_interval: float = 30.0,
        max_buffer: int = 500,
    ) -> None:
        self._store = store
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer
        self._lock = threading.Lock()
        # day -> {total, with_results, without_results}
        self._search: dict[str, dict[str, int]] = {}
        # (day, user_id, provider, work_id, fmt) -> {quantity, bytes}
        self._downloads: dict[tuple[str, str, str, str, str], dict[str, int]] = {}
        # (day, provider) -> fallos
        self._failures: dict[tuple[str, str], int] = {}
        self._count = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # --- registro de eventos -------------------------------------------------

    def record_search(self, result_total: int, day: str | None = None) -> None:
        target = day or today()
        with self._lock:
            row = self._search.setdefault(
                target, {"total": 0, "with_results": 0, "without_results": 0}
            )
            row["total"] += 1
            if result_total > 0:
                row["with_results"] += 1
            else:
                row["without_results"] += 1
            self._count += 1
        self._after_record()

    def record_download(
        self,
        provider: str,
        work_id: str,
        fmt: str,
        user_id: str | None = None,
        bytes_transferred: int = 0,
        day: str | None = None,
    ) -> None:
        target = day or today()
        user = user_id or ANON_USER
        key = (target, user, provider, work_id, fmt)
        with self._lock:
            row = self._downloads.setdefault(key, {"quantity": 0, "bytes": 0})
            row["quantity"] += 1
            row["bytes"] += max(0, bytes_transferred)
            self._count += 1
        self._after_record()

    def record_download_failure(self, provider: str, day: str | None = None) -> None:
        target = day or today()
        key = (target, provider)
        with self._lock:
            self._failures[key] = self._failures.get(key, 0) + 1
            self._count += 1
        self._after_record()

    # --- flush ---------------------------------------------------------------

    def _after_record(self) -> None:
        self._ensure_thread()
        with self._lock:
            should_flush = self._count >= self._max_buffer
        if should_flush:
            self.flush()

    def flush(self) -> None:
        """Vuelca el buffer al store; nunca propaga errores."""
        with self._lock:
            search = self._search
            downloads = self._downloads
            failures = self._failures
            self._search = {}
            self._downloads = {}
            self._failures = {}
            self._count = 0
        for day, row in search.items():
            self._safe(
                self._store.record_search_batch,
                day,
                row["total"],
                row["with_results"],
                row["without_results"],
            )
        for (day, user_id, provider, work_id, fmt), row in downloads.items():
            self._safe(
                self._store.record_download,
                day,
                user_id,
                provider,
                work_id,
                fmt,
                row["quantity"],
                row["bytes"],
            )
        for (day, provider), _ in failures.items():
            self._safe(self._store.record_download_failure, day, provider)

    @staticmethod
    def _safe(func: Callable[..., object], *args: object) -> None:
        try:
            func(*args)
        except Exception:  # noqa: BLE001 — la analítica nunca rompe la petición
            _LOGGER.warning("No se pudo registrar analítica", exc_info=True)

    # --- hilo de flush periódico --------------------------------------------

    def _ensure_thread(self) -> None:
        thread = self._thread
        if thread is not None:
            return
        with self._lock:
            if self._thread is not None:
                return
            thread = threading.Thread(target=self._loop, name="osap-analytics-flush", daemon=True)
            self._thread = thread
        thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self._flush_interval):
            self.flush()

    def close(self) -> None:
        self._stop.set()
        self.flush()
