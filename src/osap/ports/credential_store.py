from abc import ABC, abstractmethod

from ..domain.auth import AuthType, Credential


class ICredentialStore(ABC):
    """Stores and retrieves provider credentials securely (never in plaintext).

    The domain never sees the secret: it only sees `Credential` metadata with a
    `token_ref`. Retrieving the actual secret is an infrastructure concern.
    """

    @abstractmethod
    def save(self, provider_id: str, auth_type: AuthType, secret: str, permissions: tuple[str, ...]) -> Credential:
        raise NotImplementedError

    @abstractmethod
    def get(self, provider_id: str) -> Credential | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, provider_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> tuple[Credential, ...]:
        raise NotImplementedError
