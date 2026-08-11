"""V1 — Servicio de compositores (consulta pública + fusión admin).

Consulta: delegada a osap-storage con scope ``storage:read`` (pública, sin autenticación de
usuario). Fusión: exige ``UserPrincipal`` con ``role=admin`` y delega con scope
``storage:admin``. Nunca se usa ``tier`` para autorizar.
"""

from src.osap.domain.principal import Principal, UserPrincipal
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError, WorkNotFoundError
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerClient
from src.osap.ports.votes import IAuthenticator


class ComposersService:
    """Casos de uso de compositores (backend: osap-storage)."""

    def __init__(
        self,
        client: StorageComposerClient,
        authenticator: IAuthenticator,
        *,
        read_only: bool = False,
    ) -> None:
        self._client = client
        self._authenticator = authenticator
        self._read_only = read_only

    # -- consulta (pública) --------------------------------------------------

    def list_composers(
        self, q: str | None, limit: int, offset: int, review: str | None = None
    ) -> dict[str, object]:
        return self._client.list_composers(q, limit, offset, review)

    def get_composer(self, composer_id: str) -> dict[str, object] | None:
        return self._client.get_composer(composer_id)

    def composer_works(self, composer_id: str, limit: int, offset: int) -> dict[str, object]:
        return self._client.composer_works(composer_id, limit, offset)

    def get_work(self, work_id: str) -> dict[str, object] | None:
        return self._client.get_work(work_id)

    # -- administración (fusión) ---------------------------------------------

    def merge_composers(self, token: str | None, target_id: str, source_ids: list[str]) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        status, doc = self._client.merge_composers(target_id, source_ids)
        if not 200 <= status < 300:
            if status == 404:
                raise WorkNotFoundError("Composer not found")
            raise ForbiddenError(f"Storage rejected merge (HTTP {status})")
        return doc

    def create_composer(self, token: str | None, name: str) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        doc = self._client.create_composer(name)
        if doc is None:
            raise ForbiddenError("Storage rejected composer creation")
        return doc

    def review_composer(self, token: str | None, composer_id: str, review_status: str) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        status, doc = self._client.review_composer(composer_id, review_status)
        if not 200 <= status < 300:
            if status == 404:
                raise WorkNotFoundError("Composer not found")
            raise ForbiddenError(f"Storage rejected review (HTTP {status})")
        return doc

    def _ensure_writable(self) -> None:
        if self._read_only:
            raise ForbiddenError("Storage is remote; this environment is read-only")

    def require_admin(self, token: str | None) -> UserPrincipal:
        principal: Principal | None = self._authenticator.resolve(token)
        if not isinstance(principal, UserPrincipal):
            raise UnauthenticatedError("Missing or invalid access token")
        if not principal.has_role("admin"):
            raise ForbiddenError("Admin role required")
        return principal
