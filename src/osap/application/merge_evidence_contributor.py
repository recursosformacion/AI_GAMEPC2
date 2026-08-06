from src.osap.domain.evidence import EvidenceItem
from src.osap.domain.merge import MergeResult
from src.osap.ports.evidence_contributor import IEvidenceContributor


class MergeEvidenceContributor(IEvidenceContributor):
    """Adapts a `MergeResult` into `EvidenceItem` (source=MERGE)."""

    def __init__(self, result: MergeResult) -> None:
        self._result = result

    def to_evidence(self) -> tuple[EvidenceItem, ...]:
        return self._result.evidence
