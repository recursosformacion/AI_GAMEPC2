from statistics import fmean

from src.osap.application.execution_plan import WorkGroup
from src.osap.domain.evidence import EvidenceCode, EvidenceField, EvidenceItem, EvidenceSource, EvidenceStrength
from src.osap.domain.merge import (
    MergeConflict,
    MergeConflictType,
    MergeCriterion,
    MergedWorkDescriptor,
    MergePolicy,
    MergeProvenance,
    MergeResult,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.merge_service import IMergeService

_IDENTITY_FIELDS = ("catalogue_number", "opus", "composer", "title")
_SCALAR_DESCRIPTIVE = ("subtitle", "language", "key", "creation_year")
_TUPLE_DESCRIPTIVE = ("genres", "instrumentation", "voices", "aliases")


def _value(work: WorkDescriptor, field: str) -> object:
    if field == "title":
        return work.canonical_title or work.title
    return getattr(work, field)


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


class DefaultMergeService(IMergeService):
    """Consolidates the descriptive knowledge of a `WorkGroup` (V2.2.b)."""

    def merge(self, group: WorkGroup, policy: MergePolicy) -> MergeResult:
        identity: dict[str, object] = {}
        provenance: list[MergeProvenance] = []
        conflicts: list[MergeConflict] = []
        evidence: list[EvidenceItem] = []

        group_work = group.work
        for field in _IDENTITY_FIELDS:
            identity[field] = _value(group_work, field)
            differing = sorted(_identity_differing(group, field), key=lambda vs: (str(vs[0]), vs[1]))
            if differing:
                conflicts.append(
                    MergeConflict(
                        field=field,
                        conflict_type=MergeConflictType.IDENTITY_CONFLICT,
                        values=tuple(value for value, _ in differing),
                        sources=tuple(source for _, source in differing),
                    )
                )

        if _authority_conflict(group):
            ordered = sorted(group.representations, key=lambda rep: rep.provider_id.value)
            conflicts.append(
                MergeConflict(
                    field="work_authority_identifiers",
                    conflict_type=MergeConflictType.AUTHORITY_CONFLICT,
                    values=tuple(
                        "; ".join(f"{i.kind}:{i.value}" for i in rep.work_descriptor.identifiers) for rep in ordered
                    ),
                    sources=tuple(rep.provider_id.value for rep in ordered),
                )
            )

        descriptive: dict[str, object] = {}
        for field in _SCALAR_DESCRIPTIVE:
            value, prov, conflict = self._enrich_scalar(group, field, policy)
            descriptive[field] = value
            if prov is not None:
                provenance.append(prov)
                evidence.append(_field_evidence(prov))
            if conflict is not None:
                conflicts.append(conflict)
                evidence.append(_conflict_evidence(conflict))

        for field in _TUPLE_DESCRIPTIVE:
            value, prov = _enrich_tuple(group, field)
            descriptive[field] = value
            if prov is not None:
                provenance.append(prov)
                evidence.append(_field_evidence(prov))

        merged = MergedWorkDescriptor(
            title=str(identity["title"]),
            composer=_opt_str(identity["composer"]),
            catalogue_number=_opt_str(identity["catalogue_number"]),
            opus=_opt_str(identity["opus"]),
            subtitle=_opt_str(descriptive.get("subtitle")),
            language=_opt_str(descriptive.get("language")),
            key=_opt_str(descriptive.get("key")),
            creation_year=_opt_int(descriptive.get("creation_year")),
            genres=_opt_tuple(descriptive.get("genres")),
            instrumentation=_opt_tuple(descriptive.get("instrumentation")),
            voices=_opt_tuple(descriptive.get("voices")),
            aliases=_opt_tuple(descriptive.get("aliases")),
        )
        return MergeResult(
            merged_descriptor=merged,
            provenance=tuple(provenance),
            conflicts=tuple(conflicts),
            evidence=tuple(evidence),
        )

    def _enrich_scalar(
        self, group: WorkGroup, field: str, policy: MergePolicy
    ) -> tuple[object | None, MergeProvenance | None, MergeConflict | None]:
        present = [
            (_value(rep.work_descriptor, field), rep.confidence.value, rep.provider_id.value)
            for rep in group.representations
            if _is_present(_value(rep.work_descriptor, field))
        ]
        if not present:
            return None, None, None
        distinct = {str(value) for value, _, _ in present}
        if len(distinct) == 1:
            value, confidence, source = present[0]
            prov = MergeProvenance(
                field=field,
                value=value,
                source=source,
                strategy=_first_criterion(policy),
                confidence=_mean([c for _, c, _ in present]),
            )
            return value, prov, None
        value, strategy, confidence = _select(present, policy)
        prov = MergeProvenance(
            field=field, value=value, source=_source_for(present, value), strategy=strategy, confidence=confidence
        )
        ordered = sorted(present, key=lambda x: (str(x[0]), x[2]))
        conflict = MergeConflict(
            field=field,
            conflict_type=MergeConflictType.VALUE_CONFLICT,
            values=tuple(value for value, _, _ in ordered),
            sources=tuple(source for _, _, source in ordered),
        )
        return value, prov, conflict


def _enrich_tuple(group: WorkGroup, field: str) -> tuple[tuple[str, ...], MergeProvenance | None]:
    values: set[str] = set()
    sources: list[str] = []
    for rep in group.representations:
        for item in _tuple_values(_value(rep.work_descriptor, field)):
            values.add(item)
            sources.append(rep.provider_id.value)
    merged = tuple(sorted(values))
    if not merged:
        return (), None
    prov = MergeProvenance(
        field=field,
        value=merged,
        source=", ".join(sorted(set(sources))),
        strategy=_first_criterion_for_tuple(),
        confidence=1.0,
    )
    return merged, prov


def _select(present: list[tuple[object, float, str]], policy: MergePolicy) -> tuple[object, MergeCriterion, float]:
    """Deterministic selection per the first enabled criterion; order-independent."""
    for criterion in policy.enabled_criteria:
        if criterion is MergeCriterion.REPRESENTATION_CONFIDENCE:
            value, confidence, _ = max(present, key=lambda x: (x[1], str(x[0])))
            return value, criterion, confidence
        if criterion is MergeCriterion.FIELD_COMPLETENESS:
            value, confidence, _ = max(present, key=lambda x: (len(str(x[0])), str(x[0])))
            return value, criterion, confidence
        if criterion is MergeCriterion.MAJORITY:
            counts: dict[str, int] = {}
            for value, _, _ in present:
                counts[str(value)] = counts.get(str(value), 0) + 1
            chosen_key = max(counts, key=lambda k: (counts[k], k))
            chosen = next(x for x in present if str(x[0]) == chosen_key)
            return chosen[0], criterion, chosen[1]
    value, confidence, _ = max(present, key=lambda x: (x[1], str(x[0])))
    return value, MergeCriterion.REPRESENTATION_CONFIDENCE, confidence


def _source_for(present: list[tuple[object, float, str]], value: object) -> str:
    return next((source for candidate, _, source in present if str(candidate) == str(value)), present[0][2])


def _first_criterion(policy: MergePolicy) -> MergeCriterion:
    return policy.enabled_criteria[0] if policy.enabled_criteria else MergeCriterion.REPRESENTATION_CONFIDENCE


def _first_criterion_for_tuple() -> MergeCriterion:
    return MergeCriterion.FIELD_COMPLETENESS


def _identity_differing(group: WorkGroup, field: str) -> list[tuple[object, str]]:
    group_value = _value(group.work, field)
    differing: list[tuple[object, str]] = []
    for rep in group.representations:
        rep_value = _value(rep.work_descriptor, field)
        if _is_present(rep_value) and str(rep_value) != str(group_value):
            differing.append((rep_value, rep.provider_id.value))
    return differing


def _authority_conflict(group: WorkGroup) -> bool:
    reference = {identifier.kind: identifier.value for identifier in group.work.identifiers}
    for rep in group.representations:
        rep_ids = {identifier.kind: identifier.value for identifier in rep.work_descriptor.identifiers}
        if rep_ids != reference:
            return True
    return False


def _tuple_values(value: object) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(str(item) for item in value if item)
    return ()


def _field_evidence(prov: MergeProvenance) -> EvidenceItem:
    return EvidenceItem(
        source=EvidenceSource.MERGE,
        code=EvidenceCode.MERGE_FIELD,
        score=prov.confidence,
        strength=EvidenceStrength.NORMAL,
        fields=(
            EvidenceField("field", prov.field),
            EvidenceField("value", str(prov.value)),
            EvidenceField("source", prov.source),
            EvidenceField("strategy", prov.strategy.value),
        ),
    )


def _conflict_evidence(conflict: MergeConflict) -> EvidenceItem:
    return EvidenceItem(
        source=EvidenceSource.MERGE,
        code=EvidenceCode.MERGE_CONFLICT,
        score=0.0,
        strength=EvidenceStrength.WEAK,
        fields=(
            EvidenceField("field", conflict.field),
            EvidenceField("type", conflict.conflict_type.value),
        ),
    )


def _mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def _opt_str(value: object) -> str | None:
    if not _is_present(value):
        return None
    return str(value)


def _opt_int(value: object) -> int | None:
    if not _is_present(value):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _opt_tuple(value: object) -> tuple[str, ...]:
    return _tuple_values(value)
