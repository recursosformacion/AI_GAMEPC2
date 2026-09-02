"""Contrato serializable `Score` (frontera OSAP → Chorus)."""

from src.chorus.contract.bridge import contract_to_score, score_to_contract
from src.chorus.contract.model import (
    CONTRACT_SCHEMA_VERSION,
    ContractError,
    Diagnostics,
    Quality,
    ScoreContract,
    Structure,
    is_readable_contract,
)

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "ContractError",
    "Diagnostics",
    "Quality",
    "ScoreContract",
    "Structure",
    "contract_to_score",
    "is_readable_contract",
    "score_to_contract",
]
