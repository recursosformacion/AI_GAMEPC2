from dataclasses import dataclass, field

from .strategy_kind import StrategyKind
from .value_objects import ProviderId, StrategyId


@dataclass(frozen=True)
class Strategy:
    strategy_id: StrategyId
    kind: StrategyKind
    provider_id: ProviderId
    priority: int = 0
    metadata: dict[str, object] = field(default_factory=dict)
