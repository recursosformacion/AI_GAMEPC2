import json
import time
import urllib.error
import urllib.request
from typing import cast
from urllib.parse import quote

from src.osap.domain.errors import ScoreResolutionError
from src.osap.ports.cache import ICache

API_BASE_URL = "https://api.github.com"
RAW_BASE_URL = "https://raw.githubusercontent.com"

_RETRIABLE_STATUS = {403, 429, 500, 502, 503, 504}


class GitHubError(ScoreResolutionError):
    """Raised when a GitHub API request fails."""


class GitHubClient:
    """Minimal client for the GitHub REST API and raw content.

    Uses only the official GitHub REST API and raw URLs (no scraping).
    Supports: authentication token, per-request timeout, retries with backoff
    (including rate-limit handling), and an optional cache.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout: int = 20,
        retries: int = 3,
        cache: ICache | None = None,
        api_base_url: str = API_BASE_URL,
        raw_base_url: str = RAW_BASE_URL,
    ) -> None:
        self._token = token
        self._timeout = timeout
        self._retries = retries
        self._cache = cache
        self._api_base_url = api_base_url.rstrip("/")
        self._raw_base_url = raw_base_url.rstrip("/")

    def default_branch(self, owner: str, repo: str) -> str:
        payload = self._get_json(f"/repos/{owner}/{repo}")
        return str(payload.get("default_branch") or "main")  # type: ignore[attr-defined]

    def contents(self, owner: str, repo: str, path: str) -> list[dict[str, object]]:
        encoded = quote(path, safe="/")
        payload = self._get_json(f"/repos/{owner}/{repo}/contents/{encoded}")
        if isinstance(payload, list):
            return payload
        return []

    def recursive_tree(self, owner: str, repo: str, tree_sha: str) -> list[dict[str, object]]:
        payload = self._get_json(f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1")
        return list(payload.get("tree") or [])  # type: ignore[attr-defined]

    def raw(self, url: str) -> bytes:
        return self._get(url)

    def raw_url(self, owner: str, repo: str, branch: str, path: str) -> str:
        encoded = quote(path, safe="/")
        return f"{self._raw_base_url}/{owner}/{repo}/{branch}/{encoded}"

    def _get_json(self, api_path: str) -> object:
        url = f"{self._api_base_url}{api_path}"
        cached = self._cache.get(url) if self._cache else None
        if cached is not None:
            return cached
        raw = self._get(url)
        try:
            payload = cast("object", json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubError(f"Invalid JSON from {url}") from exc
        if self._cache is not None:
            self._cache.set(url, payload)
        return payload

    def _get(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                request = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                    return cast("bytes", response.read())
            except urllib.error.HTTPError as exc:
                if exc.code in _RETRIABLE_STATUS:
                    self._sleep_for_retry(exc, attempt)
                    last_error = exc
                    continue
                raise GitHubError(f"GitHub request failed ({exc.code}) for {url}") from exc
            except urllib.error.URLError as exc:
                last_error = exc
                self._sleep_backoff(attempt)
            except TimeoutError as exc:
                last_error = exc
                self._sleep_backoff(attempt)
        raise GitHubError(f"GitHub request failed after retries for {url}") from last_error

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "osap"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @staticmethod
    def _sleep_for_retry(error: urllib.error.HTTPError, attempt: int) -> None:
        delay = float(error.headers.get("Retry-After") or (2**attempt))
        time.sleep(min(delay, 10))

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2**attempt, 10))
