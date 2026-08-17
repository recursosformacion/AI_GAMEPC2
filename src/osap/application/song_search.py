"""Búsqueda de canciones/obras: variantes de query + ranking por similitud de título.

Una canción (himno, aire folclórico) no se encuentra con una única query por título. Este
módulo genera variantes (título crudo, clave canónica sin artículo/catálogo, fragmento),
busca en los proveedores y rankea los resultados por similitud de título normalizado.

Usa la capa de proveedores existente (`catalog_manager().providers()`). La recuperación es
permisiva (encontrar candidatos); la decisión final (resolution_confidence) es estricta.
"""

from __future__ import annotations

from typing import Protocol

from src.osap.api.contracts import SearchRequest
from src.osap.application.metadata_normalizer import MetadataNormalizer, title_key, title_similarity


class _Searchable(Protocol):
    def search(self, request: SearchRequest) -> tuple[object, ...]: ...


def query_variants(title: str, composer: str | None = None) -> list[str]:
    """Variantes de búsqueda para una canción (de más específica a más genérica)."""
    raw = (title or "").strip()
    if not raw:
        return []
    normalized = MetadataNormalizer.normalize_title_with_trace(raw, composer)
    variants: list[str] = []
    if composer:
        variants.append(f"{raw} {composer}".strip())
    variants.append(raw)
    key = normalized.key
    if key and key != raw.lower():
        variants.append(key)
    words = key.split()
    if len(words) > 3:
        variants.append(" ".join(words[:3]))  # fragmento inicial (folk/títulos largos)
    return list(dict.fromkeys(v for v in variants if v))


class SongSearch:
    """Busca una canción/obra en los proveedores y rankea por similitud de título."""

    def __init__(self, providers: dict[str, _Searchable | None]) -> None:
        self._providers = providers

    def search(
        self,
        title: str,
        composer: str | None = None,
        providers: list[str] | None = None,
        limit_variants: int = 25,
    ) -> list[dict[str, object]]:
        target = title_key(title)
        variants = query_variants(title, composer)
        out: list[dict[str, object]] = []
        selected = {pid: self._providers.get(pid) for pid in (providers or list(self._providers))}
        for pid, provider in selected.items():
            if provider is None:
                continue
            for variant in variants:
                try:
                    candidates = provider.search(SearchRequest(query=variant, title=variant, limit=limit_variants))
                except Exception:  # noqa: BLE001
                    continue
                for cand in candidates:
                    descriptor = getattr(cand, "work_descriptor", None)
                    ctitle = getattr(descriptor, "title", None) if descriptor is not None else None
                    if not ctitle:
                        continue
                    ckey = title_key(str(ctitle))
                    out.append(
                        {
                            "provider": pid,
                            "title": str(ctitle),
                            "composer": getattr(descriptor, "composer", None),
                            "key": ckey,
                            "score": title_similarity(target, ckey),
                        }
                    )
        # Deduplicar por (provider, title, composer).
        seen: set[tuple[str, str, object]] = set()
        unique: list[dict[str, object]] = []
        for r in out:
            dedup_key = (str(r["provider"]), str(r["title"]), r["composer"])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            unique.append(r)
        unique.sort(key=_score, reverse=True)
        return unique

    def best_match(
        self,
        title: str,
        composer: str | None = None,
        providers: list[str] | None = None,
        min_score: float = 0.6,
    ) -> dict[str, object] | None:
        results = self.search(title, composer, providers)
        for r in results:
            if _score(r) >= min_score:
                return r
        return None


def _score(item: dict[str, object]) -> float:
    value = item.get("score")
    return float(value) if isinstance(value, (int, float)) else 0.0
