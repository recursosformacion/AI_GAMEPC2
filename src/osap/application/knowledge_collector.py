from src.osap.domain.knowledge import KnowledgeBase, KnowledgeObservation
from src.osap.ports.knowledge_collector import IKnowledgeCollector


class DefaultKnowledgeCollector(IKnowledgeCollector):
    """Collects observations, normalizes (deduplicates, sorts) and builds a KnowledgeBase.

    It does not interpret: the resulting KnowledgeBase carries observations only, with
    empty facts and suggestions. Pure, deterministic, no infrastructure.
    """

    def collect(self, observations: tuple[KnowledgeObservation, ...]) -> KnowledgeBase:
        unique = sorted(set(observations), key=_observation_key)
        return KnowledgeBase(observations=tuple(unique))


def _observation_key(observation: KnowledgeObservation) -> tuple[str, str, str, str, str]:
    return (
        observation.execution_id,
        observation.source.value,
        observation.field,
        observation.value,
        observation.provider or "",
    )
