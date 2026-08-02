from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.normalization import normalize_name
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.score_ranking import ScoreRanking
from src.osap.ports.ranking_engine import IRankingEngine


class DefaultRankingEngine(IRankingEngine):
    """Orders candidates by configurable weighted criteria (highest first)."""

    def rank(
        self, candidates: tuple[CandidateRepresentation, ...], request: ResolveRequest, config: RankingConfig
    ) -> tuple[CandidateRepresentation, ...]:
        scored = [(self._score(candidate, request, config), candidate) for candidate in candidates]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return tuple(candidate for _, candidate in scored)

    def rank_detailed(
        self, candidates: tuple[CandidateRepresentation, ...], request: ResolveRequest, config: RankingConfig
    ) -> tuple[ScoreRanking, ...]:
        scored: list[ScoreRanking] = []
        for candidate in candidates:
            details, reason = self._scoring_details(candidate, request, config)
            total = sum(details.values())
            scored.append(ScoreRanking(candidate=candidate, total=total, details=details, reason=reason))
        scored.sort(key=lambda sr: sr.total, reverse=True)
        return tuple(scored)

    def _scoring_details(
        self, candidate: CandidateRepresentation, request: ResolveRequest, config: RankingConfig
    ) -> tuple[dict[str, float], str]:
        details: dict[str, float] = {}
        reasons: list[str] = []

        def _add(name: str, value: float, note: str = "") -> None:
            details[name] = value
            if note:
                reasons.append(note)

        fmt_score = self._format_score(candidate.format, request.desired_format, config)
        _add("format", fmt_score, f"formato {candidate.format.value} ({fmt_score})")

        lic_score = self._license_score(candidate, config)
        _add("license", lic_score, f"licencia ({lic_score})")

        q_score = candidate.quality.value * config.quality_weight
        _add("quality", q_score, f"calidad {candidate.quality.value}")

        c_score = self._composer_score(candidate, request, config)
        _add("composer_match", c_score, f"compositor ({c_score})")

        t_score = self._title_score(candidate, request, config)
        _add("title_match", t_score, f"título ({t_score})")

        conf_score = candidate.confidence.value * config.confidence_weight
        _add("confidence", conf_score, f"confianza ({conf_score})")

        prov_score = self._provider_score(candidate.provider_id.value, config)
        _add("provider", prov_score, f"proveedor {candidate.provider_id.value}")

        lang_score = self._language_score(candidate, request)
        _add("language", lang_score, f"idioma ({lang_score})")

        local_score = self._local_score(candidate, config)
        _add("local", local_score, f"local ({local_score})")

        return details, " · ".join(reasons) if reasons else "ranking default"

    def _score(self, candidate: CandidateRepresentation, request: ResolveRequest, config: RankingConfig) -> float:
        score = 0.0
        score += self._format_score(candidate.format, request.desired_format, config)
        score += self._license_score(candidate, config)
        score += candidate.quality.value * config.quality_weight
        score += self._composer_score(candidate, request, config)
        score += self._title_score(candidate, request, config)
        score += candidate.confidence.value * config.confidence_weight
        score += self._provider_score(candidate.provider_id.value, config)
        score += self._language_score(candidate, request)
        score += self._local_score(candidate, config)
        return score

    @staticmethod
    def _format_score(fmt: OutputFormat, desired: OutputFormat | None, config: RankingConfig) -> float:
        if desired is not None and fmt == desired:
            return 3.0
        try:
            position = config.format_order.index(fmt)
        except ValueError:
            return 0.0
        return max(0.0, float(len(config.format_order) - position)) * 0.5

    @staticmethod
    def _license_score(candidate: CandidateRepresentation, config: RankingConfig) -> float:
        if candidate.public_domain:
            return config.public_domain_weight
        if candidate.license and "public domain" in candidate.license.lower():
            return config.public_domain_weight
        return 0.0

    @staticmethod
    def _composer_score(candidate: CandidateRepresentation, request: ResolveRequest, config: RankingConfig) -> float:
        if not request.composer or not candidate.work_descriptor.composer:
            return 0.0
        if normalize_name(candidate.work_descriptor.composer) == normalize_name(request.composer):
            return config.composer_exact_weight
        return 0.0

    @staticmethod
    def _title_score(candidate: CandidateRepresentation, request: ResolveRequest, config: RankingConfig) -> float:
        if not request.title:
            return 0.0
        if normalize_name(candidate.work_descriptor.title) == normalize_name(request.title):
            return config.title_exact_weight
        return 0.0

    @staticmethod
    def _provider_score(provider_id: str, config: RankingConfig) -> float:
        if provider_id not in config.provider_order:
            return 0.0
        position = config.provider_order.index(provider_id)
        return max(0.0, float(len(config.provider_order) - position))

    @staticmethod
    def _language_score(candidate: CandidateRepresentation, request: ResolveRequest) -> float:
        if (
            request.language
            and candidate.work_descriptor.language
            and candidate.work_descriptor.language.lower() == request.language.lower()
        ):
            return 1.0
        return 0.0

    @staticmethod
    def _local_score(candidate: CandidateRepresentation, config: RankingConfig) -> float:
        if candidate.local_path is not None:
            return config.local_availability_weight
        return 0.0
