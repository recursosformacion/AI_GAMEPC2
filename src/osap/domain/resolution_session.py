"""Domain model for resolution sessions (ADR-0033 / resolution-store-v1).

A ``ResolutionSession`` is a temporary, operational storage for one resolution
operation (acquisition + matching). It is **not** a catalog: candidates are embedded per
item and no global ``works`` table exists. Session state and per-work result state are
two independent state machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ResolutionSessionStatus(Enum):
    ACQUIRING = "acquiring"
    RESOLVING = "resolving"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    EXPIRED = "expired"


class ResolutionStage(Enum):
    """Provisional vs definitive results (independent of the revision count)."""

    PROVISIONAL = "provisional"
    DEFINITIVE = "definitive"


class ProviderResultStatus(Enum):
    FETCHED = "fetched"
    RECOVERABLE_ERROR = "recoverable_error"
    END_OF_PROVIDER = "end_of_provider"


class PaginationKind(Enum):
    PAGE = "page"
    CURSOR = "cursor"


class ResolutionItemStatus(Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ResolutionPolicy:
    """Configurable per-session acquisition policy (ADR-0033)."""

    max_results_to_acquire: int = 500
    max_pages_per_provider: int = 20
    max_duration_s: int = 120
    ttl_s: int = 1800


@dataclass(frozen=True)
class ResolutionSession:
    session_id: str
    status: ResolutionSessionStatus = ResolutionSessionStatus.ACQUIRING
    query: str | None = None
    providers: tuple[str, ...] = ()
    policy: ResolutionPolicy = field(default_factory=ResolutionPolicy)
    progress: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ProviderResultPage:
    """One acquired page from a provider, identified by (session_id, provider, cursor)."""

    session_id: str
    provider: str
    pagination_kind: PaginationKind
    cursor_value: str
    next_cursor: str | None
    status: ProviderResultStatus = ProviderResultStatus.FETCHED
    payload: list[dict[str, object]] = field(default_factory=list)
    meta: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolutionItem:
    """Per-work resolution result within a session."""

    item_id: str
    session_id: str
    ref: dict[str, object]
    status: ResolutionItemStatus
    resolution_stage: ResolutionStage = ResolutionStage.PROVISIONAL
    revision: int = 1
    normalized: dict[str, object] = field(default_factory=dict)
    resolved: dict[str, object] = field(default_factory=dict)
    confidence: float = 0.0
    candidates: list[dict[str, object]] = field(default_factory=list)
    evidence: list[dict[str, object]] = field(default_factory=list)
