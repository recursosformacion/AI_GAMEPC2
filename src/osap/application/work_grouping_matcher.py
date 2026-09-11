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

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.representation_identity import RepresentationIdentity, build_identity
from src.osap.domain.normalization import stable_id

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

      1. Veto    dos compositores específicos distintos -> NO fusionar
      2. Veto    un compositor específico y el otro sin atribución/anónimo
                 (sin catálogo común)                      -> NO fusionar
      3. Veto    catálogo difiere (ambos)                  -> NO fusionar
      4. Veto    número difiere (ambos)                    -> NO fusionar
      5. Regla   catálogo igual (compositor compatible o ausente) -> fusionar (fuerte)
      6. Regla   compositor compatible == número == clave  -> fusionar
      7. Fallback compositor compatible + título muy parecido (sin conflicto) -> fusionar
      8. Si no   -> NO fusionar

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
                work_id=f"work-{stable_id(work_key)}" if work_key else None,
            )

        ca, ca_key = _composer_signal(a.work_descriptor.composer)
        cb, cb_key = _composer_signal(b.work_descriptor.composer)
        same_composer = bool(ca_key and cb_key and ca_key == cb_key)
        both_nonspecific = ca in ("missing", "anonymous") and cb in ("missing", "anonymous")
        catalog_equal = bool(na.catalog and nb.catalog and na.catalog == nb.catalog)

        # 1. Veto: dos compositores específicos y distintos -> NO fusionar.
        if ca == "specific" and cb == "specific" and ca_key != cb_key:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 2. Sin comodín: si un lado es específico y el otro está sin atribución
        #    (o es "Anonymous"/"NA"), NO usar la ausencia de compositor como comodín:
        #    solo se fusiona si ambos comparten catálogo (señal fuerte de identidad).
        one_specific = (ca == "specific") != (cb == "specific")
        if one_specific and not catalog_equal:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 3. Veto: catálogo distinto.
        if na.catalog and nb.catalog and na.catalog != nb.catalog:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 4. Veto: número distinto.
        if na.work_number and nb.work_number and na.work_number != nb.work_number:
            return decision(0.0, MergeVerdict.NOT_MERGED, [])

        # 5. Regla fuerte: catálogo igual (identificador de obra; gana a la
        #    similitud textual y a la ausencia de atribución en un lado).
        if catalog_equal:
            evidence: list[Evidence] = [
                CatalogEquivalent(_raw_catalog(a), _raw_catalog(b), na.catalog or "")
            ]
            if same_composer:
                evidence.insert(0, ExactComposer())
            return decision(0.95, MergeVerdict.MERGED, evidence)

        # 6. Regla: compositor + número + clave iguales (solo cuando la atribución
        #    es compatible: mismo compositor específico o ambos anónimos/sin dato).
        if (
            (same_composer or both_nonspecific)
            and na.work_number
            and nb.work_number
            and na.work_number == nb.work_number
            and na.key
            and nb.key
            and _keys_compatible(na.key, nb.key)
        ):
            return decision(
                0.85,
                MergeVerdict.MERGED,
                [ExactComposer(), NumberEquivalent(na.work_number), KeyEquivalent(na.key)],
            )

        # 7. Fallback por título, SOLO con atribución compatible (mismo compositor
        #    específico, o ambos sin atribución/anónimos). El caso "específico +
        #    sin dato" ya se vetó en 2 salvo catálogo igual, resuelto en 5.
        #    Reglas de metadatos:
        #      - un valor AUSENTE no es un conflicto (solo se veta si AMBOS lados
        #        aportan el campo y difieren);
        #      - títulos genéricos (núcleo corto) solo se fusionan con detalle
        #        unidireccional si hay ANCLAJE: mismo número en ambos lados, o un
        #        lado completamente sin identificadores frente a uno con catálogo.
        #        Sin anclaje, dos obras del mismo género con identificadores
        #        distintos (p. ej. preludios de Chopin) NO se fusionan.
        if not (same_composer or both_nonspecific):
            return decision(0.0, MergeVerdict.NOT_MERGED, [])
        if (
            (na.catalog and nb.catalog and na.catalog != nb.catalog)
            or (
                na.work_number
                and nb.work_number
                and na.work_number != nb.work_number
            )
            or (na.key and nb.key and not _keys_compatible(na.key, nb.key))
        ):
            return decision(0.0, MergeVerdict.NOT_MERGED, [])
        core_tokens = (na.title or "").split()
        if len(core_tokens) <= 2:
            same_number = bool(
                na.work_number and nb.work_number and na.work_number == nb.work_number
            )
            blank_a = not (na.catalog or na.work_number or na.key)
            blank_b = not (nb.catalog or nb.work_number or nb.key)
            anchored = same_number or (na.catalog and blank_b) or (nb.catalog and blank_a)
            one_sided_detail = bool(
                (na.catalog or nb.catalog)
                or (na.work_number or nb.work_number)
                or (na.key or nb.key)
            )
            if one_sided_detail and not anchored:
                return decision(0.0, MergeVerdict.NOT_MERGED, [])
        sim = _token_similarity(na.title or "", nb.title or "")
        if sim >= _TITLE_FALLBACK_SIM:
            ev: list[Evidence] = [TitleSimilarity(similarity=round(sim, 2), confidence=round(sim, 2))]
            if same_composer:
                ev.insert(0, ExactComposer())
            return decision(0.55, MergeVerdict.MERGED, ev)

        # 8. Por defecto: NO fusionar.
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


# Marcadores de "sin atribución" tratados como ausencia (nunca como comodín de fusión).
_UNKNOWN_COMPOSER_MARKERS = {"", "na", "n/a", "unknown", "anon", "anonymous", "attrib."}


def _composer_signal(raw: str | None) -> tuple[str, str]:
    """Clasifica el compositor en una señal para la decisión.

    Devuelve (categoría, clave):
      - ("missing", "")       — sin dato;
      - ("anonymous", "anonymous") — marcadores anónimos (Anonymous/NA/anon/trad);
      - ("specific", clave)   — compositor concreto (clave normalizada de igualdad).
    """
    text = (raw or "").strip()
    if not text:
        return "missing", ""
    low = text.lower()
    if low in _UNKNOWN_COMPOSER_MARKERS:
        return "anonymous", "anonymous"
    key = MetadataNormalizer.comparison_composer(text)
    if not key or key == "anonymous":
        return "anonymous", "anonymous"
    return "specific", key


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


def _keys_compatible(a: str, b: str) -> bool:
    """Dos claves son compatibles si son iguales o comparten tónica sin modo explícito
    en al menos un lado ("A" ≈ "A major"). Dos modos explícitos distintos NO lo son
    ("G major" ≠ "G minor"). La ausencia de clave se resuelve antes de llamar aquí."""
    if a == b:
        return True
    mode_a = _key_mode(a)
    mode_b = _key_mode(b)
    if mode_a and mode_b:
        return False
    return _key_tonic(a) == _key_tonic(b)


def _key_tonic(key: str) -> str:
    return key.split(" ", 1)[0].strip()


def _key_mode(key: str) -> str:
    parts = key.split(" ", 1)
    return parts[1].strip().lower() if len(parts) > 1 else ""
