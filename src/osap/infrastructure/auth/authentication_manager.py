from src.osap.domain.auth import AuthType, Credential
from src.osap.infrastructure.auth.secure_credential_store import SecureCredentialStore


class AuthenticationManager:
    """Manages provider authentication.

    Generic: OSAP only uses the user's credentials, never performs scraping or
    stores passwords in the domain. Credentials are stored encrypted.
    """

    def __init__(self, store: SecureCredentialStore) -> None:
        self._store = store

    def login(
        self, provider_id: str, auth_type: AuthType, secret: str, permissions: tuple[str, ...] = ()
    ) -> Credential:
        return self._store.save(provider_id, auth_type, secret, permissions)

    def logout(self, provider_id: str) -> None:
        self._store.delete(provider_id)

    def status(self, provider_id: str) -> Credential | None:
        return self._store.get(provider_id)

    def list(self) -> tuple[Credential, ...]:
        return self._store.list()

    def secret(self, provider_id: str) -> str | None:
        return self._store.secret(provider_id)
