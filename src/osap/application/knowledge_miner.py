from src.osap.domain.knowledge import (
    KnowledgeBase,
    KnowledgeFact,
    KnowledgeFactType,
    KnowledgeObservation,
    KnowledgeSuggestion,
    KnowledgeSuggestionType,
)
from src.osap.ports.knowledge_miner import IKnowledgeMiner

_MIN_COUNT_FOR_SUGGESTION = 2


class DefaultKnowledgeMiner(IKnowledgeMiner):
    """Aggregates observations into Facts and derives Suggestions.

    Deterministic and reproducible: mining the same KnowledgeBase always yields exactly
    the same Facts and Suggestions. Never modifies the input (immutable by construction).
    """

    def mine(self, base: KnowledgeBase) -> KnowledgeBase:
        facts = self._facts(base.observations)
        suggestions = self._suggestions(facts)
        return KnowledgeBase(observations=base.observations, facts=facts, suggestions=suggestions)

    def _facts(self, observations: tuple[KnowledgeObservation, ...]) -> tuple[KnowledgeFact, ...]:
        groups: dict[tuple[str, str], list[KnowledgeObservation]] = {}
        for observation in observations:
            groups.setdefault((observation.field, observation.value), []).append(observation)

        facts: list[KnowledgeFact] = []
        for (field, value), items in groups.items():
            ordered = sorted(items, key=lambda o: (o.execution_id, o.source.value, o.provider or ""))
            facts.append(
                KnowledgeFact(
                    fact_type=KnowledgeFactType.FREQUENCY,
                    field=field,
                    value=value,
                    count=len(ordered),
                    sources=tuple(sorted({o.source for o in ordered}, key=lambda s: s.value)),
                    observation_ids=tuple(sorted({o.execution_id for o in ordered})),
                )
            )
        facts.sort(key=_fact_key)
        return tuple(facts)

    def _suggestions(self, facts: tuple[KnowledgeFact, ...]) -> tuple[KnowledgeSuggestion, ...]:
        suggestions: list[KnowledgeSuggestion] = []
        for fact in facts:
            if fact.count >= _MIN_COUNT_FOR_SUGGESTION:
                sources = ", ".join(source.value for source in fact.sources)
                suggestions.append(
                    KnowledgeSuggestion(
                        suggestion_type=KnowledgeSuggestionType.ADD_ALIAS,
                        field=fact.field,
                        source_value=fact.value,
                        target_value=fact.value,
                        reason=f"value observed {fact.count} times across {sources}",
                        fact_ids=(fact.signature,),
                    )
                )
        suggestions.sort(key=_suggestion_key)
        return tuple(suggestions)


def _fact_key(fact: KnowledgeFact) -> tuple[str, str, str]:
    return (fact.fact_type.value, fact.field, fact.value)


def _suggestion_key(suggestion: KnowledgeSuggestion) -> tuple[str, str, str, str]:
    return (
        suggestion.suggestion_type.value,
        suggestion.field,
        suggestion.source_value,
        suggestion.target_value,
    )
