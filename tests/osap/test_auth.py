from pathlib import Path

from src.osap.domain.auth import AuthType
from src.osap.infrastructure.auth import AuthenticationManager, SecureCredentialStore


class TestSecureCredentialStore:
    def _store(self, tmp_path: Path) -> SecureCredentialStore:
        return SecureCredentialStore(tmp_path / "creds.db", "test-master-key")

    def test_save_get_list_delete(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        cred = store.save("musescore", AuthType.OAUTH2, "super-secret", ("read", "download"))
        assert cred.provider_id == "musescore"
        assert store.get("musescore") == cred
        assert store.secret("musescore") == "super-secret"
        assert [c.provider_id for c in store.list()] == ["musescore"]
        store.delete("musescore")
        assert store.get("musescore") is None

    def test_secret_not_in_plaintext(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        store.save("imslp", AuthType.TOKEN, "secret-token", ())
        raw = (tmp_path / "creds.db").read_bytes()
        assert b"secret-token" not in raw

    def test_secret_requires_same_key(self, tmp_path: Path) -> None:
        store_a = SecureCredentialStore(tmp_path / "creds.db", "key-a")
        store_a.save("provider", AuthType.API_KEY, "my-secret", ())
        store_b = SecureCredentialStore(tmp_path / "creds.db", "key-b")
        # Wrong key must not recover the original secret.
        assert store_b.secret("provider") != "my-secret"


class TestAuthenticationManager:
    def test_login_status_logout(self, tmp_path: Path) -> None:
        manager = AuthenticationManager(SecureCredentialStore(tmp_path / "creds.db", "key"))
        manager.login("musescore", AuthType.OAUTH2, "s3cr3t")
        assert manager.status("musescore") is not None
        assert manager.secret("musescore") == "s3cr3t"
        manager.logout("musescore")
        assert manager.status("musescore") is None
