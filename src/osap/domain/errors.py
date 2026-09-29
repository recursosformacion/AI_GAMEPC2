class DomainError(Exception):
    """Base error for domain-level failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ScoreResolutionError(DomainError):
    """Raised when a musical work cannot be resolved to a Score."""


class ResourceUnavailableError(DomainError):
    """A needed resource is not installed and could not be obtained automatically.

    ``code`` is an optional machine-readable reason (e.g. ``"index_missing"``)
    so callers can distinguish *why* a resource is unavailable without parsing
    human-facing messages.
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class ResourceNeedsApprovalError(ResourceUnavailableError):
    """A resource requires user approval (too large, requires license acceptance)."""


class DatasetOperationError(DomainError):
    """Base error for dataset operations."""


class DatasetCancelledError(DatasetOperationError):
    """Raised when a dataset operation is cancelled by the user."""


class AiNotConfiguredError(DomainError):
    """La IA de atribución no está configurada en osap-storage (falta la API key).

    osap-storage responde 503 en este caso; osap-api lo traduce a un 503 explícito para el
    panel de revisión, sin afectar al resto del mantenimiento.
    """


class ProposalNotAssignableError(DomainError):
    """La propuesta no se puede aceptar (p. ej. persona sin coincidencia exacta en storage).

    osap-storage responde 409: aceptar sin persona resuelta duplicaría o inventaría identidad.
    """


