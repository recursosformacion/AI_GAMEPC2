"""Composer identity resolution port (v1).

A `IComposerResolver` turns a `ResolverQuery` (context about a composer/work, never a
storage `composer_id`) into a list of `ResolverCandidate` with each provider's own
confidence and evidence. Resolvers never decide: the `ComposerResolutionEngine`
normalizes centrally, merges candidates by canonical identity and emits the final
verdict (`resolved | ambiguous | not_found`).

See `docs/osap/composer-resolution.md`.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ResolverCategory(StrEnum):
    CATALOG = "catalog"  # CPDL, IMSLP, ...: aportan work_match
    IDENTITY = "identity"  # MusicBrainz, Wikidata, VIAF: autoridad + IDs externos


@dataclass(frozen=True)
class ResolverRepresentation:
    """A known representation of the work, used as extra context by a resolver."""

    title: str
    provider: str
    format: str


@dataclass(frozen=True)
class ResolverQuery:
    """Context handed to a resolver. Never carries a storage `composer_id`.

    `composer` is optional: the primary signal is the work. When present, the caller's
    composer name is only secondary evidence (it may be corrupt/mojibake), never a
    requirement.
    """

    work_title: str | None = None
    composer: str | None = None
    work_catalog: str | None = None
    work_year: int | None = None
    source_provider: str | None = None
    source_work_id: str | None = None
    representations: tuple[ResolverRepresentation, ...] = ()


@dataclass(frozen=True)
class ResolverEvidence:
    """A single piece of evidence from one source (evidence, not "the truth")."""

    kind: str  # work_match | composer_match | external_id | alias
    confidence: float
    work_title: str | None = None
    work_catalog: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ResolverCandidate:
    """What a single source believes the composer identity is."""

    name: str
    confidence: float
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, str] = field(default_factory=dict)
    evidence: tuple[ResolverEvidence, ...] = ()


@dataclass(frozen=True)
class ResolverResult:
    """Response from a single resolver."""

    provider: str
    candidates: tuple[ResolverCandidate, ...]
    error: str | None = None


class IComposerResolver(Protocol):
    provider_id: str
    categories: frozenset[ResolverCategory]

    async def resolve(self, query: ResolverQuery) -> ResolverResult: ...
