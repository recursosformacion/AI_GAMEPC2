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

    def get_composer_biography(self, composer_id: str) -> dict[str, object] | None:
        return self._client.get_composer_biography(composer_id)

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

    def add_alias(self, token: str | None, composer_id: str, alias: str) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        doc = self._client.add_alias(composer_id, alias)
        if doc is None:
            raise ForbiddenError("Storage rejected alias creation")
        return doc

    def list_aliases(self, token: str | None, composer_id: str) -> list[dict[str, object]]:
        self.require_admin(token)
        return self._client.list_aliases(composer_id)

    def move_alias(
        self, token: str | None, alias_id: int, from_composer_id: str, target_composer_id: str
    ) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        doc = self._client.move_alias(alias_id, from_composer_id, target_composer_id)
        if doc is None:
            raise ForbiddenError("Storage rejected alias move")
        return doc

    def promote_alias(self, token: str | None, composer_id: str, alias_id: int) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        doc = self._client.promote_alias(composer_id, alias_id)
        if doc is None:
            raise ForbiddenError("Storage rejected alias promote")
        return doc

    def set_attribution(self, token: str | None, composer_ids: list[str], attribution_type: str) -> dict[str, object]:
        self.require_admin(token)
        self._ensure_writable()
        doc = self._client.set_attribution(composer_ids, attribution_type)
        if doc is None:
            raise ForbiddenError("Storage rejected set-attribution")
        return doc

    def composer_review_stats(self, token: str | None) -> dict[str, int]:
        self.require_admin(token)
        return self._client.composer_review_stats()

    def storage_statistics(self) -> dict[str, int]:
        return self._client.storage_statistics()

    def catalogues(self, prefix: str | None = None, composer: str | None = None) -> list[dict[str, object]]:
        return self._client.catalogues(prefix, composer)

    def storage_web_admin_url(self) -> str:
        return self._client.storage_web_admin_url()

    def storage_base_url(self) -> str:
        return self._client.storage_base_url()

    def storage_admin_token(self) -> str:
        return self._client.storage_admin_token()

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
