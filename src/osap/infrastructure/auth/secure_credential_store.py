import hashlib
import sqlite3
from pathlib import Path
from typing import cast

from src.osap.domain.auth import AuthType, Credential


class SecureCredentialStore:
    """Stores credentials encrypted at rest using a keyed stream cipher.

    No cryptographic dependency is required: a keystream is derived from a
    master key (provided via the ``master_key`` argument) with ``pbkdf2_hmac``
    and XORed with the secret bytes. The secret is never stored in plaintext.
    """

    def __init__(self, path: Path, master_key: str) -> None:
        self._path = path
        self._master_key = master_key.encode("utf-8")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save(self, provider_id: str, auth_type: AuthType, secret: str, permissions: tuple[str, ...]) -> Credential:
        encrypted = self._encrypt(secret.encode("utf-8"))
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO credentials(provider_id, auth_type, secret, permissions) VALUES (?,?,?,?)",
                (provider_id, auth_type.value, encrypted, "\n".join(permissions)),
            )
        return Credential(provider_id=provider_id, auth_type=auth_type, token_ref=provider_id, permissions=permissions)

    def get(self, provider_id: str) -> Credential | None:
        row = self._row(provider_id)
        if row is None:
            return None
        return Credential(
            provider_id=provider_id,
            auth_type=AuthType(row["auth_type"]),
            token_ref=provider_id,
            permissions=tuple(row["permissions"].split("\n")) if row["permissions"] else (),
        )

    def delete(self, provider_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM credentials WHERE provider_id=?", (provider_id,))

    def list(self) -> tuple[Credential, ...]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT provider_id, auth_type, permissions FROM credentials ORDER BY provider_id"
            ).fetchall()
        result = []
        for row in rows:
            result.append(
                Credential(
                    provider_id=row[0],
                    auth_type=AuthType(row[1]),
                    token_ref=row[0],
                    permissions=tuple(row[2].split("\n")) if row[2] else (),
                )
            )
        return tuple(result)

    def secret(self, provider_id: str) -> str | None:
        row = self._row(provider_id)
        if row is None or row["secret"] is None:
            return None
        try:
            return self._decrypt(row["secret"]).decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _row(self, provider_id: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT provider_id, auth_type, secret, permissions FROM credentials WHERE provider_id=?",
                (provider_id,),
            ).fetchone()
        return cast("sqlite3.Row | None", row)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS credentials ("
                "provider_id TEXT PRIMARY KEY, auth_type TEXT, secret BLOB, permissions TEXT)"
            )

    def _encrypt(self, data: bytes) -> bytes:
        keystream = self._keystream(len(data))
        return bytes(a ^ b for a, b in zip(data, keystream, strict=False))

    def _decrypt(self, data: bytes) -> bytes:
        return self._encrypt(data)

    def _keystream(self, length: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._master_key, b"osap-credential-store", 100_000, dklen=length)
