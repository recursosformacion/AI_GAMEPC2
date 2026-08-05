from enum import Enum


class CostLevel(Enum):
    """Cost of querying a provider (money, quota, rate limit or latency).

    The orchestrator only needs to know how expensive a provider is to query,
    not why. Canonical V2 levels (aligned from the former FREE/LOW/MEDIUM/HIGH).
    """

    FREE = "free"
    CHEAP = "cheap"
    NORMAL = "normal"
    EXPENSIVE = "expensive"
