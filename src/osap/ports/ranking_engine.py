from abc import ABC, abstractmethod

from ..domain.candidate_representation import CandidateRepresentation
from ..domain.ranking_config import RankingConfig
from ..domain.resolve_request import ResolveRequest
from ..domain.score_ranking import ScoreRanking


class IRankingEngine(ABC):
    """Orders CandidateRepresentations for a request using configurable criteria."""

    @abstractmethod
    def rank(
        self, candidates: tuple[CandidateRepresentation, ...], request: ResolveRequest, config: RankingConfig
    ) -> tuple[CandidateRepresentation, ...]:
        raise NotImplementedError

    @abstractmethod
    def rank_detailed(
        self, candidates: tuple[CandidateRepresentation, ...], request: ResolveRequest, config: RankingConfig
    ) -> tuple[ScoreRanking, ...]:
        raise NotImplementedError
