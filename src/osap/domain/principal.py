"""V1 — Principal (identidad del llamante).

Tres tipos de principal: ``anonymous``, ``user`` y ``service``. ``tier`` NO forma parte del
Principal operativo en esta fase (no se consulta, no se resuelve, no se persiste). ``role`` y
``email_verified`` sí se usan para autorizar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class Principal(ABC):
    """Base de identidad del llamante."""

    @property
    @abstractmethod
    def type(self) -> str:
        """"anonymous" | "user" | "service"."""

    @property
    def is_anonymous(self) -> bool:
        return self.type == "anonymous"

    @property
    def is_user(self) -> bool:
        return self.type == "user"

    @property
    def is_service(self) -> bool:
        return self.type == "service"


@dataclass(frozen=True)
class AnonymousPrincipal(Principal):
    """Petición sin identidad autenticada."""

    type: str = "anonymous"
    user_id: None = None
    service_id: None = None


@dataclass(frozen=True)
class UserPrincipal(Principal):
    """Usuario autenticado por osap-auth. Identidad = ``user_id`` (UUID opaco)."""

    user_id: str
    roles: tuple[str, ...] = ("user",)
    email_verified: bool = True
    type: str = "user"
    service_id: None = None

    def has_role(self, role: str) -> bool:
        return role in self.roles


@dataclass(frozen=True)
class ServicePrincipal(Principal):
    """Identidad técnica (``service_id`` = ``client_id``)."""

    service_id: str
    scopes: tuple[str, ...] = ()
    type: str = "service"
    user_id: None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
