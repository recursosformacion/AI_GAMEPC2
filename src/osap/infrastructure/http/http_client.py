import json
import urllib.error
import urllib.request
from typing import cast
from urllib.parse import urlencode

from src.osap.domain.errors import ScoreResolutionError


class HttpError(ScoreResolutionError):
    """Raised when an HTTP request fails."""


class HttpClient:
    """Minimal, injectable HTTP client used by infrastructure adapters.

    Wrapped behind an interface so providers can be tested offline with fakes.
    """

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        request = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                return cast("bytes", response.read())
        except urllib.error.URLError as exc:
            raise HttpError(f"HTTP request failed for {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise HttpError(f"HTTP request timed out for {url}") from exc

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> object:
        raw = self.get(url, headers=headers)
        try:
            return cast("object", json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpError(f"Invalid JSON response from {url}") from exc

    @staticmethod
    def build_url(base_url: str, path: str, params: dict[str, str]) -> str:
        separator = "&" if "?" in base_url else "?"
        query = urlencode(params)
        return f"{base_url}{path}{separator}{query}"
