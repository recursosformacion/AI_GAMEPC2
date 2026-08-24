"""Scored matching between musical representations.

The ``WorkGroupingMatcher`` decides whether two representations belong to the same
work by a weighted agreement across fields. It returns a ``MergeDecision`` whose
``evidence`` is a list of structured, explainable objects:

    MergeDecision(
        score=0.85,
        decision=MERGED,
        evidence=[
            ExactComposer(weight=0.35, confidence=1.0),
            CatalogEquivalent(raw_a="KV 618", raw_b="K.618", normalized="k 618",
                              weight=0.20, confidence=1.0),
            TitleSimilarity(similarity=0.98, algorithm="token_jaccard",
                            weight=0.30, confidence=0.98),
        ],
        work_key="...",
        work_id="work-9d83a3d2",
    )

Evidence is a shared *language*: every object declares its ``label``, ``weight``
and ``confidence`` plus its own structured fields. Both a rule-based matcher and
a future AI policy can produce or consume the exact same objects, so the rest of
the pipeline never changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.representation_identity import RepresentationIdentity, build_identity

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation

# Umbral por defecto de fusión (fallback por título).
_DEFAULT_THRESHOLD = 0.5
# Similitud mínima de título para la regla de fallback.
_TITLE_FALLBACK_SIM = 0.6


class MergeVerdict(StrEnum):
    """Final binary outcome of a comparison."""

    MERGED = "MERGED"
    NOT_MERGED = "NOT_MERGED"


@dataclass(frozen=True)
class ExactComposer:
    """Both representations share the same (expanded) composer."""

    weight: float = 0.35
    confidence: float = 1.0
    label: str = "composer"

    def __str__(self) -> str:
        return "composer"


@dataclass(frozen=True)
class TitleSimilarity:
    """The core title tokens overlap with the given similarity in [0, 1]."""

    similarity: float
    algorithm: str = "token_jaccard"
    weight: float = 0.30
    confidence: float = 0.0
    label: str = "title_similarity"

    def __str__(self) -> str:
        return f"title_similarity({self.similarity:.2f})"


@dataclass(frozen=True)
class CatalogEquivalent:
    """Catalogues differ in raw form but normalize to the same value."""

    raw_a: str
    raw_b: str
    normalized: str
    weight: float = 0.20
    confidence: float = 1.0
    label: str = "catalog"

    def __str__(self) -> str:
        return f"catalog({self.raw_a!r}={self.raw_b!r})"


@dataclass(frozen=True)
class NumberEquivalent:
    """Work numbers agree."""

    value: str
    weight: float = 0.15
    confidence: float = 1.0
    label: str = "number"

    def __str__(self) -> str:
        return f"number({self.value})"


@dataclass(frozen=True)
class KeyEquivalent:
    """Musical keys agree."""

    value: str
    weight: float = 0.10
    confidence: float = 1.0
    label: str = "key"

    def __str__(self) -> str:
        return f"key({self.value})"


# A piece of evidence is any of the concrete evidence objects above.
Evidence = ExactComposer | TitleSimilarity | CatalogEquivalent | NumberEquivalent | KeyEquivalent


@dataclass(frozen=True)
class MergeDecision:
    """The outcome of comparing two representations.

    ``score`` is the weighted, clamped FINAL score; ``decision`` is the binary
    verdict; ``evidence`` are structured, explainable reasons (each with weight
    and confidence); ``breakdown`` holds the per-field agreement (0..1, ``None``
    when not comparable); ``work_key``/``work_id`` identify the merged work.
    """

    score: float
    decision: MergeVerdict
    evidence: tuple[Evidence, ...]
    confidence: float
    breakdown: tuple[tuple[str, float | None], ...] = ()
    work_key: str | None = None
    work_id: str | None = None

    @property
    def merged(self) -> bool:
        return self.decision is MergeVerdict.MERGED

    def evidence_labels(self) -> tuple[str, ...]:
        return tuple(e.label for e in self.evidence)

    def reason_labels(self) -> tuple[str, ...]:
        """Backward-compatible alias for :meth:`evidence_labels`."""
        return self.evidence_labels()


class WorkGroupingMatcher:
    """Decides whether two representations are the same work (V2.0 grouping).

    Procedimiento de DECISIÓN POR REGLAS sobre la identidad normalizada
    (RepresentationIdentity). Sin regexes y sin comparar texto: solo igualdades.

      1. Veto    composer difiere            -> NO fusionar
      2. Veto    catálogo difiere (ambos)    -> NO fusionar
      3. Veto    número difiere (ambos)      -> NO fusionar
      4. Regla   composer == catalog         -> fusionar (fuerte)
      5. Regla   composer == número == clave -> fusionar
      6. Fallback composer == título muy parecido (sin conflicto) -> fusionar (baja confianza)
      7. Si no   -> NO fusionar

    Cada paso emite la misma ``MergeDecision`` (evidencia + explicación).
    """

    def __init__(self, threshold: float = _DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    def compare(self, a: CandidateRepresentation, b: CandidateRepresentation) -> MergeDecision:
        na = build_identity(a.work_descriptor.title, a.work_descriptor.composer)
        nb = build_identity(b.work_descriptor.title, b.work_descriptor.composer)

        def decision(score: float, verdict: MergeVerdict, evidence: list[Evidence]) -> MergeDecision:
            work_key = na.signature()
            return MergeDecision(
                score=score,
                decision=verdict,
                evidence=tuple(evidence),
                confidence=self._confidence(score, a.confidence.value, b.confidence.value),
                breakdown=_breakdown(na, nb),
                work_key=work_key,
                work_id=f"work-{abs(hash(work_key))}" if work_key else None,
            )

        composer_same = bool(na.composer and nb.composer and na.composer == nb.composer)
        composer_both = bool(na.composer and nb.composer)

        # 1. Veto: compositor distinto.
        if composer_both and not composer_same:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 2. Veto: catálogo distinto.
        if na.catalog and nb.catalog and na.catalog != nb.catalog:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 3. Veto: número distinto.
        if na.work_number and nb.work_number and na.work_number != nb.work_number:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 4. Regla fuerte: catálogo igual (dato más fuerte; los vetos de
        #    compositor/catálogo ya descartaron las contradicciones).
        if na.catalog and nb.catalog and na.catalog == nb.catalog:
            evidence: list[Evidence] = [CatalogEquivalent(_raw_catalog(a), _raw_catalog(b), na.catalog)]
            if composer_same:
                evidence.insert(0, ExactComposer())
            return decision(0.95, MergeVerdict.MERGED, evidence)

        # 5. Regla: compositor + número + clave iguales.
        if (
            composer_same
            and na.work_number
            and nb.work_number
            and na.work_number == nb.work_number
            and na.key
            and nb.key
            and na.key == nb.key
        ):
            return decision(
                0.85,
                MergeVerdict.MERGED,
                [ExactComposer(), NumberEquivalent(na.work_number), KeyEquivalent(na.key)],
            )

        # 6. Fallback: título muy parecido, sin conflicto estructurado. La regla 1
        #    ya vetó compositores contradictorios, así que aquí basta la similitud
        #    de título (funciona aunque el compositor sea desconocido en un lado).
        #    PROTECCIÓN: cuando el título reducido es genérico (p. ej. 'prelude',
        #    'sonata'), un catálogo/número/clave presente en un solo lado es señal de
        #    obra distinta y NO se fusiona. Con título específico (≥3 tokens, p. ej.
        #    'ave verum corpus') el título resuelve la ambigüedad y se permite.
        core_tokens = (na.title or "").split()
        generic_title = len(core_tokens) <= 2
        if generic_title:
            if (na.catalog or nb.catalog) and na.catalog != nb.catalog:
                return decision(0.0, MergeVerdict.NOT_MERGED, [])
            if (na.work_number or nb.work_number) and na.work_number != nb.work_number:
                return decision(0.0, MergeVerdict.NOT_MERGED, [])
            if (na.key or nb.key) and na.key != nb.key:
                return decision(0.0, MergeVerdict.NOT_MERGED, [])
        else:
            if (
                na.catalog
                and nb.catalog
                and na.catalog != nb.catalog
            ) or (
                na.work_number
                and nb.work_number
                and na.work_number != nb.work_number
            ) or (
                na.key
                and nb.key
                and na.key != nb.key
            ):
                return decision(0.0, MergeVerdict.NOT_MERGED, [])
        sim = _token_similarity(na.title or "", nb.title or "")
        if sim >= _TITLE_FALLBACK_SIM:
            ev: list[Evidence] = [TitleSimilarity(similarity=round(sim, 2), confidence=round(sim, 2))]
            if composer_same:
                ev.insert(0, ExactComposer())
            return decision(0.55, MergeVerdict.MERGED, ev)

        # 7. Por defecto: NO fusionar.
        return decision(0.0, MergeVerdict.NOT_MERGED, [])

    def should_merge(self, decision: MergeDecision) -> bool:
        return decision.score >= self._threshold

    @staticmethod
    def _confidence(score: float, conf_a: float, conf_b: float) -> float:
        rep = (conf_a + conf_b) / 2.0
        return max(0.0, min(0.7 * score + 0.3 * rep, 1.0))


def _breakdown(na: RepresentationIdentity, nb: RepresentationIdentity) -> tuple[tuple[str, float | None], ...]:
    composer: float | None = None
    if na.composer and nb.composer:
        composer = 1.0 if na.composer == nb.composer else 0.0
    catalog: float | None = None
    if na.catalog and nb.catalog:
        catalog = 1.0 if na.catalog == nb.catalog else 0.0
    elif na.catalog or nb.catalog:
        catalog = 0.5
    number: float | None = None
    if na.work_number and nb.work_number:
        number = 1.0 if na.work_number == nb.work_number else 0.0
    elif na.work_number or nb.work_number:
        number = 0.5
    key: float | None = None
    if na.key and nb.key:
        key = 1.0 if na.key == nb.key else 0.0
    elif na.key or nb.key:
        key = 0.5
    sim = _token_similarity(na.title or "", nb.title or "")
    return (("composer", composer), ("title", round(sim, 2)), ("catalog", catalog), ("number", number), ("key", key))


def _raw_catalog(rep: CandidateRepresentation) -> str:
    meta = extract_metadata(rep.work_descriptor.title)
    return meta.catalogue_raw or meta.catalogue or ""


def _token_similarity(a: str, b: str) -> float:
    """Token Jaccard similarity between two comparison titles."""
    if a == b:
        return 1.0
    ta = set(a.split())
    tb = set(b.split())
    if not ta and not tb:
        return 1.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0
