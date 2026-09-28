"""W1: verificación real de firma/claims en osap-api (JWKS por kid).

Un token legítimo se acepta; manipulado, con firma inválida, kid desconocido o expirado se
rechaza, y `require_admin` no puede atravesarse con un JWT fabricado.
"""

from __future__ import annotations

import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.osap.application.votes_service import VotesService
from src.osap.domain.votes import UnauthenticatedError
from src.osap.infrastructure.auth.token_authenticator import (
    JwksJwtAuthenticator,
    JwtAuthenticator,
)

_ISS = "https://auth.osap"
_AUD = "osap-api"
_KID = "k1"


def _rsa_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private_pem, public_pem


def _jwks(public_pem: str, kid: str = _KID) -> dict[str, Any]:
    from jwt.algorithms import RSAAlgorithm

    public_key = serialization.load_pem_public_key(public_pem.encode())
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _token(
    private_pem: str,
    *,
    kid: str = _KID,
    sub: str = "u1",
    roles: tuple[str, ...] = ("admin",),
    iss: str = _ISS,
    aud: str = _AUD,
    exp: int | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "exp": exp if exp is not None else now + 300,
        "iat": now - 1,
        "jti": "j1",
        "token_use": "user",
        "roles": list(roles),
    }
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})


def _auth(jwks: dict[str, Any]) -> JwksJwtAuthenticator:
    return JwksJwtAuthenticator(
        jwks_url="https://auth.osap/auth/.well-known/jwks.json",
        issuer=_ISS,
        audience=_AUD,
        jwks_provider=lambda: jwks,
    )


def test_token_legitimo_aceptado() -> None:
    private_pem, public_pem = _rsa_pair()
    principal = _auth(_jwks(public_pem)).resolve(_token(private_pem))
    assert principal is not None
    assert principal.has_role("admin")


def test_roles_manipulados_rechazado() -> None:
    private_pem, public_pem = _rsa_pair()
    authenticator = _auth(_jwks(public_pem))
    token = _token(private_pem, roles=("user",))

    header, payload, signature = token.split(".")
    claims = json.loads(jwt.utils.base64url_decode(payload.encode()).decode())
    claims["roles"] = ["admin"]
    forged_payload = jwt.utils.base64url_encode(json.dumps(claims).encode()).decode()
    forged = f"{header}.{forged_payload}.{signature}"

    # El decodificador sin verificar sí lo creería (comportamiento antiguo)...
    legacy = JwtAuthenticator().resolve(forged)
    assert legacy is not None and legacy.has_role("admin")
    # ...pero el verificador lo rechaza.
    assert authenticator.resolve(forged) is None


def test_firma_incorrecta_rechazado() -> None:
    _, public_pem = _rsa_pair()
    other_private_pem, _ = _rsa_pair()
    assert _auth(_jwks(public_pem)).resolve(_token(other_private_pem)) is None


def test_kid_desconocido_rechazado() -> None:
    private_pem, public_pem = _rsa_pair()
    assert _auth(_jwks(public_pem, kid=_KID)).resolve(_token(private_pem, kid="otro")) is None


def test_expirado_rechazado() -> None:
    private_pem, public_pem = _rsa_pair()
    expired = int(time.time()) - 3600
    assert _auth(_jwks(public_pem)).resolve(_token(private_pem, exp=expired)) is None


def test_require_admin_no_se_atraviesa_con_jwt_fabricado() -> None:
    _, public_pem = _rsa_pair()
    authenticator = _auth(_jwks(public_pem))

    header = jwt.utils.base64url_encode(
        json.dumps({"alg": "RS256", "typ": "JWT", "kid": _KID}).encode()
    ).decode()
    now = int(time.time())
    payload = jwt.utils.base64url_encode(
        json.dumps(
            {
                "sub": "attacker",
                "token_use": "user",
                "roles": ["admin"],
                "email_verified": True,
                "iss": _ISS,
                "aud": _AUD,
                "exp": now + 300,
                "iat": now - 1,
                "jti": "x",
            }
        ).encode()
    ).decode()
    forged = f"{header}.{payload}.AAAA"

    service = VotesService(None, None, authenticator)  # type: ignore[arg-type]
    with pytest.raises(UnauthenticatedError):
        service.require_admin(forged)


def test_require_admin_con_token_legitimo_admin_pasa() -> None:
    private_pem, public_pem = _rsa_pair()
    service = VotesService(None, None, _auth(_jwks(public_pem)))  # type: ignore[arg-type]
    assert service.require_admin(_token(private_pem)).has_role("admin")
