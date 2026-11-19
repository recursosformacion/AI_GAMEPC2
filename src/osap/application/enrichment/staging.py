"""Staging de candidatos de enriquecimiento (tabla ``enrichment_candidates``).

Solo escribe en su propia tabla de staging; nunca en `works`, `persons` ni el índice.
La promoción a datos de dominio se hace tras revisión (fase posterior).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pymysql
from pymysql.cursors import DictCursor

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.osap.application.enrichment.models import EnrichmentCandidate

_DDL = """
CREATE TABLE IF NOT EXISTS enrichment_candidates (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entity_type VARCHAR(16) NOT NULL,
  entity_key VARCHAR(255) NOT NULL,
  field VARCHAR(64) NOT NULL,
  value TEXT NOT NULL,
  value_hash CHAR(64) NOT NULL,
  source VARCHAR(32) NOT NULL,
  evidence_url VARCHAR(1024) NOT NULL DEFAULT '',
  confidence DECIMAL(3,2) NOT NULL DEFAULT 0.00,
  license VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(16) NOT NULL DEFAULT 'new',
  fetched_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_enrich (entity_type, entity_key, field, source, value_hash),
  KEY idx_enrich_entity (entity_type, entity_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_INSERT = """
INSERT INTO enrichment_candidates
  (entity_type, entity_key, field, value, value_hash, source, evidence_url,
   confidence, license, fetched_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  confidence = VALUES(confidence),
  evidence_url = VALUES(evidence_url),
  license = VALUES(license),
  fetched_at = VALUES(fetched_at)
"""


def value_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def connect(
    host: str, user: str, password: str, database: str, port: int = 3306
) -> Any:
    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def ensure_schema(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(_DDL)
    conn.commit()


def stage_candidates(conn: Any, candidates: Iterable[EnrichmentCandidate]) -> int:
    rows = [
        (
            c.entity_type,
            c.entity_key,
            c.field,
            c.value,
            value_hash(c.value),
            c.source,
            c.evidence_url,
            round(c.confidence, 2),
            c.license,
            c.fetched_at or _now(),
        )
        for c in candidates
    ]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(_INSERT, rows)
    conn.commit()
    return len(rows)
