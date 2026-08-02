from dataclasses import dataclass, field
from enum import Enum


class AuthType(Enum):
    TOKEN = "token"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    PASSWORD = "password"


@dataclass(frozen=True)
class AuthRequirements:
    """What a provider needs to authenticate."""

    requires_auth: bool = False
    auth_type: AuthType | None = None
    permissions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Credential:
    """Metadata about a stored credential.

    The secret itself is never stored here: the domain only holds a reference
    (``token_ref``). The actual secret lives encrypted in infrastructure.
    """

    provider_id: str
    auth_type: AuthType
    token_ref: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
