import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from src.osap.domain.errors import ScoreResolutionError
from src.osap.ports.cache import ICache


class MediaWikiError(ScoreResolutionError):
    """Raised when a MediaWiki API call fails."""


class MediaWikiClient:
    """Typed client for the IMSLP MediaWiki API (imslp.org/api.php).

    Encapsulates search, category traversal, wikitext retrieval and file
    download. Respects a configurable rate limit, supports an optional cache,
    and manages the ``imslpdisclaimeraccepted`` cookie transparently.
    """

    def __init__(
        self,
        base_url: str = "https://imslp.org",
        *,
        cache: ICache | None = None,
        rate_limit: float = 1.0,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        verify: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_url = f"{self._base_url}/api.php"
        self._cache = cache
        self._rate = rate_limit
        self._ua = user_agent
        self._last_call = 0.0
        self._context = self._build_ssl_context(verify)

    def search(self, query: str, namespace: int = 0, limit: int = 10) -> list[dict[str, object]]:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": str(namespace),
            "srlimit": str(limit),
            "format": "json",
            "srwhat": "text",
        }
        payload = self._get(params)
        result = payload.get("query", {})
        if isinstance(result, dict):
            items = result.get("search")
            if isinstance(items, list):
                return cast("list[dict[str, object]]", items)
        return []

    def category_members(self, category: str, limit: int = 50) -> list[dict[str, object]]:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": str(limit),
            "format": "json",
            "cmtype": "page",
        }
        payload = self._get(params)
        result = payload.get("query", {})
        if isinstance(result, dict):
            items = result.get("categorymembers")
            if isinstance(items, list):
                return cast("list[dict[str, object]]", items)
        return []

    def page_revisions(self, title: str) -> str:
        params = {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "content",
            "rvlimit": "1",
            "format": "json",
        }
        payload = self._get(params)
        pages = payload["query"]["pages"]
        page = next(iter(pages.values())) if pages else {}
        revisions = page.get("revisions", []) if isinstance(page, dict) else []
        return str(revisions[0].get("*", "")) if revisions else ""

    def image_info(self, file_title: str) -> dict[str, object]:
        params = {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url|descriptionurl|size|mime|sha1",
            "format": "json",
        }
        payload = self._get(params)
        pages = payload["query"]["pages"]
        for page in pages.values():
            if isinstance(page, dict):
                info = page.get("imageinfo")
                if isinstance(info, list) and info:
                    return cast("dict[str, object]", info[0])
        return {}

    def page_images(self, title: str) -> list[str]:
        params = {
            "action": "query",
            "titles": title,
            "prop": "images",
            "format": "json",
            "imlimit": "max",
        }
        payload = self._get(params)
        pages = payload.get("query", {}).get("pages", {})
        if isinstance(pages, dict):
            for page in pages.values():
                if isinstance(page, dict):
                    images = page.get("images")
                    if isinstance(images, list):
                        return [str(img["title"]) for img in images if isinstance(img, dict)]
        return []

    def images_info_batch(self, titles: list[str]) -> list[dict[str, object]]:
        """Query imageinfo for up to 50 file titles in a single API call."""
        if not titles:
            return []
        batch = "|".join(titles[:50])
        params = {
            "action": "query",
            "titles": batch,
            "prop": "imageinfo",
            "iiprop": "url|descriptionurl|size|mime|sha1",
            "format": "json",
        }
        payload = self._get(params)
        pages = payload.get("query", {}).get("pages", {})
        results: list[dict[str, object]] = []
        if isinstance(pages, dict):
            for page in pages.values():
                if isinstance(page, dict):
                    info = page.get("imageinfo")
                    if isinstance(info, list):
                        results.extend(cast("list[dict[str, object]]", info))
        return results

    def download(self, url: str) -> bytes:
        if url.startswith("//"):
            url = f"https:{url}"
        elif url.startswith("http://"):
            url = f"https:{url[len('http:') :]}"
        req = urllib.request.Request(url, headers=self._headers())
        req.add_header("Cookie", "imslpdisclaimeraccepted=yes")
        try:
            with urllib.request.urlopen(req, timeout=30, context=self._context) as response:  # noqa: S310
                return cast("bytes", response.read())
        except urllib.error.HTTPError as exc:
            raise MediaWikiError(f"MediaWiki download error ({exc.code}) for {url}") from exc
        except urllib.error.URLError as exc:
            raise MediaWikiError(f"MediaWiki download connection error for {url}: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise MediaWikiError(f"MediaWiki download failed for {url}: {exc}") from exc

    def _get(self, params: dict[str, str]) -> Any:
        query = urllib.parse.urlencode(params)
        url = f"{self._api_url}?{query}"
        cached = self._cache.get(url) if self._cache else None
        if cached is not None:
            return cached
        self._wait()
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=20, context=self._context) as resp:  # noqa: S310
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise MediaWikiError(f"MediaWiki API error ({exc.code}) for {url}") from exc
        except urllib.error.URLError as exc:
            raise MediaWikiError(f"MediaWiki API connection error for {url}: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise MediaWikiError(f"MediaWiki API request failed for {url}: {exc}") from exc
        import json

        payload = cast("dict[str, object]", json.loads(raw.decode("utf-8")))
        if self._cache is not None:
            self._cache.set(url, payload)
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Connection": "keep-alive",
        }

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._rate:
            time.sleep(self._rate - elapsed)
        self._last_call = time.monotonic()

    @staticmethod
    def _build_ssl_context(verify: bool) -> ssl.SSLContext | None:
        if not verify:
            return ssl._create_unverified_context()  # noqa: S323
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            return None  # use system default
