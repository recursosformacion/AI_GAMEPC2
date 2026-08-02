from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str | None = None
    composer: str | None = None
    genre: str | None = None
    language: str | None = None
    voices: tuple[str, ...] = ()
    format: str | None = None
    min_quality: str | None = None


class ResolveRequest(BaseModel):
    query: str | None = None
    composer: str | None = None
    voices: tuple[str, ...] = ()
    format: str | None = None
    index: int | None = None


@dataclass(frozen=True)
class WorkDTO:
    id: str
    title: str
    display_title: str | None = None
    canonical_title: str | None = None
    canonical_key: str | None = None
    composer: str | None = None
    catalog: str | None = None
    genre: str | None = None
    voices: tuple[str, ...] = field(default_factory=tuple)
    duration: float | None = None
    public_domain: bool | None = None
    representation_count: int = 0
    providers: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RepresentationDTO:
    provider: str
    format: str
    quality: str
    downloadable: bool


@dataclass(frozen=True)
class JobDTO:
    job_id: str
    type: str
    state: str
    progress: int = 0
    result: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PreviewDTO:
    work: str
    composer: str | None = None
    catalog: str | None = None
    representations: tuple[RepresentationDTO, ...] = field(default_factory=tuple)
