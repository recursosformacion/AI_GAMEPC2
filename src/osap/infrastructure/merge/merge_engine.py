from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.score import Score
from src.osap.ports.merge_engine import IMergeEngine


class MergeEngine(IMergeEngine):
    """Combines several representations into a new Score.

    Architecture only: the actual merging algorithm (OpenScore + Audiveris +
    human corrections) is implemented in a later phase. The contract is fixed
    now so the pipeline and the API can depend on it.
    """

    def merge(self, sources: tuple[AcquisitionResult, ...]) -> Score:
        if not sources:
            raise ScoreResolutionError("Cannot merge an empty set of sources")
        raise NotImplementedError("Merge algorithm is not implemented yet")
