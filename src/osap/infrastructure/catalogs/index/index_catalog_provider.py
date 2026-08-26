"""Proveedor de catálogo virtual respaldado por el índice local de osap-api.

El índice (`index_works` + `index_representations` en la BD operativa de osap-api)
es el resultado normalizado y deduplicado de varios catálogos. Este proveedor busca
en el índice y produce candidatos con el `provider_id` real de cada representación
(omr, imslp, mutopia, musicbrainz), de modo que el orquestador puede responder desde
el índice (rápido, determinista) y solo consultar en vivo a los proveedores no
indexados (p. ej. RISM).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import TYPE_CHECKING

import pymysql
from pymysql.cursors import DictCursor

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    ProviderId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.catalog_provider import ICatalogProvider

if TYPE_CHECKING:
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.resolve_request import ResolveRequest

logger = logging.getLogger("osap.index_provider")

_FORMAT_BY_VALUE: dict[str, OutputFormat] = {
    "musicxml": OutputFormat.MUSICXML,
    "mxl": OutputFormat.MUSICXML,
    "xml": OutputFormat.MUSICXML,
    "mei": OutputFormat.MEI,
    "midi": OutputFormat.MIDI,
    "mid": OutputFormat.MIDI,
    "pdf": OutputFormat.PDF,
    "json": OutputFormat.SCORE,
}

_INDEXED_PROVIDERS = ("omr", "imslp", "mutopia", "musicbrainz")

# Prefijos de catálogo: BWV 232 == BWV.232 == Bwv 232; KV 618 == K. 618 == K618.
# Incluye sinónimos (Köchel: K./KV/Kochel Verzeichnis/Koch. Ver./Köchel).
_CATALOGUE_PREFIX_RE = re.compile(
    r"(?i)(?<![a-z0-9])"
    r"((?:bwv|kv|kochel(?:[^a-z0-9]+ver(?:zeichnis)?)?|k\u00f6chel|koch(?:\.?\s*ver)?|k\.?|op\.?|opus|hob\.?|d\.?|r\.?|wq\.?|s\.?|l\.?|twv)\s*\.?\s*(?:no\.?\s*)?)"
    r"(\d{1,4}[a-z]?(?:[-/.]\d{1,3}[a-z]?)*|[IVXLCDM]{1,6}\s*:\s*\d{1,3})"
)


def _catalogue_normalized(text: str) -> str:
    """Normaliza un catálogo escrito a su clave: 'K. 618' / 'KV 618' / 'k618' -> 'k618'.

    Los sinónimos de Köchel convergen a 'k': 'Koch. Ver. No. 618' -> 'k618'.
    """
    if not text:
        return ""
    m = _CATALOGUE_PREFIX_RE.search(text)
    if not m:
        return ""
    prefix = unicodedata.normalize("NFKD", m.group(1)).encode("ascii", "ignore").decode().lower()
    key_prefix = "k" if re.search(r"koch|kochel|k\.|kv", prefix) else re.sub(r"[^a-z0-9]", "", prefix)
    number = re.sub(r"[^a-z0-9]", "", m.group(2).lower())
    return f"{key_prefix}{number}"


def _catalogue_variants(text: str) -> list[str]:
    """Variantes compactas de un catálogo para matchear contra `title` de forma difusa.

    'D 547' -> ['D 547', 'D.547', 'D547', 'D 547']; 'KV 618' -> ['KV 618', 'KV.618',
    'KV618', 'KV 618']. Cada variante conserva mayúsculas del prefijo para LIKE.
    """
    m = _CATALOGUE_PREFIX_RE.search(text)
    if not m:
        return []
    prefix = m.group(1).strip().rstrip(".")
    number = m.group(2)
    plain_prefix = prefix.replace(".", "")
    variants = {
        f"{prefix} {number}",
        f"{prefix}.{number}",
        f"{prefix}{number}",
        f"{plain_prefix}{number}",
        f"{plain_prefix} {number}",
    }
    return [v for v in sorted(variants) if v]


class IndexCatalogProvider(ICatalogProvider):
    """Búsqueda sobre el índice local (works + representaciones).

    Es un proveedor *offline*: nunca hace llamadas de red. `search()` consulta
    `index_works` filtrado por título/compositor/catálogo y devuelve un candidato
    por representación indexada, con `provider_id` = proveedor real.
    """

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        user: str = "osap2027",
        password: str = "2027osapdb",
        database: str = "osap-api",
        name: str = "index",
        max_results: int = 400,
    ) -> None:
        self._provider_id = ProviderId(name)
        self._host = host
        self._user = user
        self._password = password
        self._database = database
        self._max_results = max_results
        self._fulltext_available: bool | None = None

    def _has_fulltext(self, conn: pymysql.connections.Connection[DictCursor]) -> bool:
        """Detecta el índice FULLTEXT `ft_idx_title_composer` (una sola vez).

        Si la migración de esquema todavía no se ha aplicado (deploy previo), la
        búsqueda cae a LIKE hasta que el índice exista. Nunca lanza.
        """
        if self._fulltext_available is not None:
            return self._fulltext_available
        available = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND table_name = 'index_works' "
                    "AND index_name = 'ft_idx_title_composer'"
                )
                row = cur.fetchone()
                available = bool(row and row["n"] > 0)
        except Exception:  # noqa: BLE001
            available = False
        self._fulltext_available = available
        return available

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    @property
    def indexed_providers(self) -> tuple[str, ...]:
        """Proveedores cubiertos por el índice: SOLO se consultan en vivo NO (se sirven del índice)."""
        return _INDEXED_PROVIDERS

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=True,
            supports_download=False,
            formats=tuple(_FORMAT_BY_VALUE.values()),
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId(self._provider_id.value),
            name=self._provider_id.value,
            provider_id=self.provider_id,
            source="osap-api index",
            status=CatalogStatus.AVAILABLE,
        )

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        try:
            conn = pymysql.connect(
                host=self._host,
                user=self._user,
                password=self._password,
                database=self._database,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=True,
            )
        except pymysql.err.OperationalError as exc:
            logger.warning("index provider: MySQL no disponible (%s)", exc)
            return ()
        try:
            use_fulltext = self._has_fulltext(conn)
            query, args = _build_sql(request, self._max_results, use_fulltext=use_fulltext)
            if query is None:
                return ()
            with conn.cursor() as cur:
                cur.execute(query, args)
                rows = cur.fetchall()
        except pymysql.err.OperationalError as exc:
            logger.warning("index provider: error consultando índice (%s)", exc)
            return ()
        finally:
            conn.close()
        return tuple(_row_to_candidate(r) for r in rows)

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(SearchRequest.from_resolve(request))
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        # El índice no descarga en vivo: las representaciones llevan download_url
        # (OMR/Mutopia) o view_url (IMSLP/MusicBrainz) y el API las sirve por redirect.
        raise ScoreResolutionError(f"Index candidate {candidate.candidate_id.value} is not downloadable")


def _build_sql(
    request: SearchRequest, max_results: int, use_fulltext: bool = False
) -> tuple[str | None, tuple[object, ...]]:
    """Construye la consulta al índice a partir de la SearchRequest.

    Devuelve (None, ()) si no hay términos utilizables (no conviene escanear 354k filas).
    El `query` libre matchea título O compositor; los campos explícitos (title, composer,
    catalogue) se aplican estrictamente sobre sus columnas.
    """
    title = (request.title or "").strip()
    composer = (request.composer or "").strip()
    catalogue = (request.catalogue or "").strip()
    free = (request.query or "").strip()
    if not title and not composer and not catalogue and not free:
        return None, ()
    clauses: list[str] = []
    args: list[object] = []
    if title:
        clauses.append("i.title LIKE %s")
        args.append(f"%{title}%")
    if composer:
        clauses.append("i.composer_name LIKE %s")
        args.append(f"%{composer}%")
    if catalogue:
        cat_key = _catalogue_normalized(catalogue)
        clauses.append(
            "(i.catalogue LIKE %s OR i.catalogue_key LIKE %s OR i.catalogue_key LIKE %s OR i.catalogue LIKE %s)"
        )
        args.extend((f"%{catalogue}%", f"%{catalogue.lower()}%", f"%{cat_key}%", f"%{cat_key}%"))
    if free:
        m = _CATALOGUE_PREFIX_RE.search(free)
        key = _catalogue_normalized(m.group(0)) if m else ""
        variants = _catalogue_variants(free) if m else []
        is_pure_catalogue = False
        if m:
            rest = re.sub(r"(?i)[^a-z0-9]+", "", free.replace(m.group(1), "").replace(m.group(2), ""))
            is_pure_catalogue = not rest
        free_clauses: list[str] = []
        free_args: list[object] = []
        if is_pure_catalogue:
            # Query que ES un catálogo (ej. "K 618", "D 547", "BWV 232"): buscar por
            # catálogo normalizado y variantes del título, sin LIKE de texto libre
            # (prefijos cortos como K/D generan falsos positivos en título/compositor).
            if key:
                free_clauses.append("i.catalogue_key LIKE %s")
                free_args.append(f"%{key}%")
            for variant in variants:
                free_clauses.append("i.title LIKE %s")
                free_args.append(f"%{variant}%")
        else:
            # Query libre general (o texto + catálogo): matchea título/compositor y,
            # si lleva catálogo, también las variantes.
            #
            # FULLTEXT (si el índice existe): un único token >=3 chars sin catálogo
            # usa MATCH(title, composer_name) BOOLEAN con sufijo '*' -> usa índice, sin
            # full scan. Cualquier otro caso (multi-palabra, catálogo, token corto) cae
            # a LIKE (correcto, aunque full scan).
            free_tokens = free.split()
            single_token = len(free_tokens) == 1 and len(free_tokens[0]) >= 3
            if use_fulltext and single_token and not key and not variants:
                # Prefijo BOOLEAN: 'moz*' matchea tokens que empiezan por 'moz'
                # (mozart, Mozzafiato...) usando el índice FULLTEXT (sin full scan).
                free_clauses = ["MATCH(i.title, i.composer_name) AGAINST(%s IN BOOLEAN MODE)"]
                free_args = [f"{free}*"]
            else:
                free_clauses = ["i.title LIKE %s", "i.composer_name LIKE %s"]
                free_args = [f"%{free}%", f"%{free}%"]
            if key:
                free_clauses.append("i.catalogue_key LIKE %s")
                free_args.append(f"%{key}%")
                for variant in variants:
                    free_clauses.append("i.title LIKE %s")
                    free_args.append(f"%{variant}%")
        clauses.append("(" + " OR ".join(free_clauses) + ")")
        args.extend(free_args)
    where = " AND ".join(clauses)
    providers = tuple(_INDEXED_PROVIDERS)
    if request.allowed_providers:
        allowed = {p.value for p in request.allowed_providers}
        providers = tuple(p for p in providers if p in allowed)
        if not providers:
            return None, ()
    sql = (
        "SELECT i.id, i.title, i.composer_name, i.catalogue, i.year, "
        "r.provider, r.format, r.download_url, r.available, r.quality "
        "FROM index_representations r "
        "JOIN index_works i ON i.id = r.work_id "
        f"WHERE {where} AND r.provider IN ({', '.join(['%s'] * len(providers))}) "
        "ORDER BY i.title LIMIT %s"
    )
    args.extend(providers)
    args.append(max_results)
    return sql, tuple(args)


def _row_to_candidate(row: dict[str, object]) -> CandidateRepresentation:
    fmt = _FORMAT_BY_VALUE.get(str(row.get("format") or ""), OutputFormat.SCORE)
    provider = ProviderId(str(row.get("provider") or "index"))
    work_id = WorkId(f"index-{row['id']}")
    composer = str(row.get("composer_name") or "") or None
    title = str(row.get("title") or "")
    catalogue = str(row.get("catalogue") or "") or None
    year = row.get("year")
    year_str = str(year or "").strip()
    creation_year = int(year_str) if year_str.isdigit() else None
    descriptor = WorkDescriptor(
        work_id=work_id,
        title=title,
        composer=composer,
        catalogue_number=catalogue,
        creation_year=creation_year,
    )
    url = str(row.get("download_url") or "") or None
    # OMR/Mutopia tienen fichero descargable (redirect 302 del storage/proveedor).
    # IMSLP/MusicBrainz guardan el permlink/página del registro -> view_url, sin fichero.
    pid = provider.value
    if pid in ("omr", "mutopia"):
        download_url = url
        view_url = None
        downloadable = bool(url)
    else:
        download_url = None
        view_url = url
        downloadable = False
    return CandidateRepresentation(
        candidate_id=CandidateId(f"index-{row['id']}-{pid}"),
        work_descriptor=descriptor,
        provider_id=provider,
        format=fmt,
        origin="index",
        license=None,
        confidence=Confidence(0.7),
        download_url=download_url,
        view_url=view_url,
        downloadable=downloadable,
        public_domain=True,
        metadata={"indexed": True, "available": bool(row.get("available"))},
    )
