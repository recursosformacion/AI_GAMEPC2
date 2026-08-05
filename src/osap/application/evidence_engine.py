from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.evidence import Evidence, EvidenceMetrics, EvidenceReason, EvidenceReasonKind
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.score_ranking import ScoreRanking

_CONFIDENCE_THRESHOLD = 0.9
_HIGH_QUALITY = (QualityLevel.FULL_NOTATION, QualityLevel.HUMAN_VALIDATED)
_QUALITY_MAX = 4.0


class EvidenceEngine:
    """Answers one question: why did OSAP choose this representation?

    It never decides, never searches and never downloads. It only builds a
    structured `Evidence` for an already-chosen candidate, using the ranking
    scores and the request.
    """

    def explain(
        self,
        chosen: CandidateRepresentation,
        request: ResolveRequest,
        scores: tuple[ScoreRanking, ...],
    ) -> Evidence:
        chosen_score = self._score_for(chosen, scores)
        return Evidence(
            provider_id=chosen.provider_id,
            reasons=tuple(self._reasons(chosen, request)),
            metrics=self._metrics(chosen),
            checksum=chosen.checksum,
            ranking_score=chosen_score.total if chosen_score is not None else 0.0,
        )

    @staticmethod
    def _reasons(chosen: CandidateRepresentation, request: ResolveRequest) -> list[EvidenceReason]:
        reasons = [
            EvidenceReason(
                EvidenceReasonKind.CONFIDENCE,
                chosen.confidence.value >= _CONFIDENCE_THRESHOLD,
                f"{chosen.confidence.value:.3f}",
            ),
            EvidenceReason(
                EvidenceReasonKind.FORMAT,
                request.desired_format is None or chosen.format == request.desired_format,
                chosen.format.value,
            ),
            EvidenceReason(
                EvidenceReasonKind.PUBLIC_DOMAIN,
                _is_public_domain(chosen),
                str(bool(chosen.public_domain or _license_is_public_domain(chosen))).lower(),
            ),
            EvidenceReason(
                EvidenceReasonKind.QUALITY,
                chosen.quality in _HIGH_QUALITY
                or (request.min_quality is not None and chosen.quality.value >= request.min_quality.value),
                chosen.quality.name,
            ),
            EvidenceReason(
                EvidenceReasonKind.COMPLETENESS,
                chosen.completeness >= 1.0,
                f"{chosen.completeness:.3f}",
            ),
            EvidenceReason(
                EvidenceReasonKind.CHECKSUM,
                chosen.checksum is not None,
                chosen.checksum or "",
            ),
        ]
        return reasons

    @staticmethod
    def _metrics(chosen: CandidateRepresentation) -> EvidenceMetrics:
        return EvidenceMetrics(
            confidence=chosen.confidence.value,
            quality=min(chosen.quality.value / _QUALITY_MAX, 1.0),
            completeness=chosen.completeness,
        )

    @staticmethod
    def _score_for(chosen: CandidateRepresentation, scores: tuple[ScoreRanking, ...]) -> ScoreRanking | None:
        for score in scores:
            if score.candidate.candidate_id == chosen.candidate_id:
                return score
        return None


def _is_public_domain(candidate: CandidateRepresentation) -> bool:
    return bool(candidate.public_domain) or _license_is_public_domain(candidate)


def _license_is_public_domain(candidate: CandidateRepresentation) -> bool:
    return candidate.license is not None and "public domain" in candidate.license.lower()
