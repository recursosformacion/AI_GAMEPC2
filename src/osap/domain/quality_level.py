from enum import Enum


class QualityLevel(Enum):
    UNREADABLE = 0
    PARTIAL_STRUCTURE = 1
    BASIC_MELODY = 2
    FULL_NOTATION = 3
    HUMAN_VALIDATED = 4
