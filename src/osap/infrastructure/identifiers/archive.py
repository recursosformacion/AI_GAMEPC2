"""Archivo de identificadores — por obra y por autor (cada cosa en su sitio).

Almacén en ficheros JSON bajo `data/authority`: `composers.json` (por compositor) y
`works.json` (por obra). Guarda los identificadores persistentes (ISNI, IPI, ISWC,
Wikidata, VIAF, MusicBrainz, LCCN) que alimentan la reconstrucción de works. No es un
catálogo: es el archivo de autoridades/IDs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ComposerRecord:
    composer_key: str
    canonical_name: str = ""
    aliases: list[str] = field(default_factory=list)
    isni: str | None = None
    ipi: str | None = None
    wikidata: str | None = None
    viaf: str | None = None
    musicbrainz: str | None = None
    lccn: str | None = None
    source: str = ""
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ComposerRecord:
        return cls(
            composer_key=str(data.get("composer_key", "")),
            canonical_name=str(data.get("canonical_name") or ""),
            aliases=[str(a) for a in raw_aliases] if isinstance((raw_aliases := data.get("aliases")), list) else [],
            isni=_opt_str(data.get("isni")),
            ipi=_opt_str(data.get("ipi")),
            wikidata=_opt_str(data.get("wikidata")),
            viaf=_opt_str(data.get("viaf")),
            musicbrainz=_opt_str(data.get("musicbrainz")),
            lccn=_opt_str(data.get("lccn")),
            source=str(data.get("source") or ""),
            updated_at=str(data.get("updated_at") or _now()),
        )


@dataclass
class WorkRecord:
    work_key: str
    title: str = ""
    catalog: str | None = None
    composer_ref: str | None = None
    iswc: str | None = None
    wikidata_work: str | None = None
    musicbrainz_work: str | None = None
    source: str = ""
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> WorkRecord:
        return cls(
            work_key=str(data.get("work_key", "")),
            title=str(data.get("title") or ""),
            catalog=_opt_str(data.get("catalog")),
            composer_ref=_opt_str(data.get("composer_ref")),
            iswc=_opt_str(data.get("iswc")),
            wikidata_work=_opt_str(data.get("wikidata_work")),
            musicbrainz_work=_opt_str(data.get("musicbrainz_work")),
            source=str(data.get("source") or ""),
            updated_at=str(data.get("updated_at") or _now()),
        )


def _opt_str(value: object) -> str | None:
    return str(value) if value is not None else None


class IdentifierArchive:
    """Archivo de identificadores por autor y por obra (cada cosa en su sitio)."""

    def __init__(self, root: str | Path = "data/authority") -> None:
        self._composers_path = Path(root) / "composers.json"
        self._works_path = Path(root) / "works.json"
        self._composers: dict[str, dict[str, object]] = self._load(self._composers_path)
        self._works: dict[str, dict[str, object]] = self._load(self._works_path)

    @staticmethod
    def _load(path: Path) -> dict[str, dict[str, object]]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return {}

    def _save(self, path: Path, data: dict[str, dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- por autor ---

    def upsert_composer(self, record: ComposerRecord) -> None:
        existing = self._composers.get(record.composer_key)
        merged = {**(existing or {}), **record.to_dict()}
        merged["updated_at"] = _now()
        self._composers[record.composer_key] = merged
        self._save(self._composers_path, self._composers)

    def get_composer(self, composer_key: str) -> ComposerRecord | None:
        data = self._composers.get(composer_key)
        return ComposerRecord.from_dict(data) if data else None

    def all_composers(self) -> list[ComposerRecord]:
        return [ComposerRecord.from_dict(d) for d in self._composers.values()]

    # --- por obra ---

    def upsert_work(self, record: WorkRecord) -> None:
        existing = self._works.get(record.work_key)
        merged = {**(existing or {}), **record.to_dict()}
        merged["updated_at"] = _now()
        self._works[record.work_key] = merged
        self._save(self._works_path, self._works)

    def get_work(self, work_key: str) -> WorkRecord | None:
        data = self._works.get(work_key)
        return WorkRecord.from_dict(data) if data else None

    def all_works(self) -> list[WorkRecord]:
        return [WorkRecord.from_dict(d) for d in self._works.values()]
