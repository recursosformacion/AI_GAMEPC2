"""V1 — Store de votos y estadísticas vía el contrato de osap-storage.

osap-api **no persiste votos en su propia BD**: los votos viven en osap-storage. Este
cliente implementa :class:`IVoteStore` llamando a los endpoints del contrato de Storage.
Un conflicto de unicidad en Storage (409) se traduce en ``DuplicateVoteError``.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from src.osap.domain.votes import (
    ComposerStats,
    DuplicateVoteError,
    WorkNotFoundError,
    WorkStats,
    WorkVote,
)
from src.osap.ports.service_token import IServiceTokenProvider
from src.osap.ports.votes import IVoteStore

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class StorageUnavailableError(Exception):
    """osap-storage no respondió o no implementa el contrato de votos."""


class StorageVoteStore(IVoteStore):
    """Persistencia de votos/estadísticas en osap-storage (HTTP)."""

    def __init__(
        self,
        base_url: str = "https://storage.openmusicrepository.com",
        timeout: int = 15,
        token_provider: IServiceTokenProvider | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token_provider = token_provider

    def insert_vote(self, vote: WorkVote) -> WorkVote:
        # El contrato de storage registra el voto en /works/{work_id}/votes (work_id en la URL,
        # integer) con body {user_id, vote}. El user_id es dato de negocio.
        payload: dict[str, object] = {"user_id": vote.user_id, "vote": vote.vote}
        status, doc = self._call(
            "POST", f"/api/v1/works/{_q(vote.work_id)}/votes", payload, scope="storage:write"
        )
        if status == 409:
            raise DuplicateVoteError("Already voted for this work today")
        if status == 404:
            raise WorkNotFoundError("Work not found")
        if not 200 <= status < 300:
            raise StorageUnavailableError(f"Storage vote rejected: HTTP {status}")
        return vote

    def work_statistics(self, work_id: str) -> WorkStats | None:
        status, doc = self._call("GET", f"/api/v1/works/{_q(work_id)}/statistics", scope="storage:read")
        if not 200 <= status < 300 or not isinstance(doc, dict):
            return None
        return _work_stats(work_id, doc)

    def composer_statistics(self, composer_id: str) -> ComposerStats | None:
        status, doc = self._call("GET", f"/api/v1/composers/{_q(composer_id)}/statistics", scope="storage:read")
        if not 200 <= status < 300 or not isinstance(doc, dict):
            return None
        return _composer_stats(composer_id, doc)

    def anonymize_user(self, user_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        status, doc = self._call("POST", "/api/v1/votes/anonymize", {"user_id": user_id}, scope="storage:write")
        if not 200 <= status < 300 or not isinstance(doc, dict):
            return (), ()
        works = doc.get("work_ids") or []
        composers = doc.get("composer_ids") or []
        return tuple(str(w) for w in works), tuple(str(c) for c in composers)

    def total_votes(self) -> int:
        status, doc = self._call("GET", "/api/v1/votes/overview", scope="storage:read")
        if not 200 <= status < 300 or not isinstance(doc, dict):
            return 0
        return int(doc.get("total_votes") or 0)

    def top_works(self, limit: int = 20) -> list[WorkStats]:
        status, doc = self._call("GET", f"/api/v1/votes/top-works?limit={limit}", scope="storage:read")
        out: list[WorkStats] = []
        for item in doc if isinstance(doc, list) else []:
            if isinstance(item, dict):
                out.append(_work_stats(_as_str(item.get("work_id")), item))
        return out

    def top_composers(self, limit: int = 20) -> list[ComposerStats]:
        status, doc = self._call("GET", f"/api/v1/votes/top-composers?limit={limit}", scope="storage:read")
        out: list[ComposerStats] = []
        for item in doc if isinstance(doc, list) else []:
            if isinstance(item, dict):
                out.append(_composer_stats(_as_str(item.get("composer_id")), item))
        return out

    def last_execution(self) -> dict[str, object] | None:
        status, doc = self._call("GET", "/api/v1/votes/executions/last", scope="storage:read")
        return doc if isinstance(doc, dict) else None

    # -- helpers -------------------------------------------------------------

    def _call(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        scope: str = "storage:read",
    ) -> tuple[int, object]:
        url = self._base_url + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers: dict[str, str] = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._token_provider is not None:
            headers["Authorization"] = f"Bearer {self._token_provider.token((scope,))}"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (storage contract)
                raw = response.read()
                try:
                    doc: object = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    doc = {}
                return response.status, doc
        except urllib.error.HTTPError as exc:
            return exc.code, {}
        except Exception as exc:
            raise StorageUnavailableError(str(exc)) from exc


def _q(value: str) -> str:
    return urllib.parse.quote(value)


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_str(value: object) -> str:
    return str(value) if value is not None else ""


def _work_stats(work_id: str, doc: dict[str, object]) -> WorkStats:
    return WorkStats(
        work_id=work_id,
        vote_count=_as_int(doc.get("vote_count")),
        vote_sum=_as_int(doc.get("vote_sum")),
        vote_average=_as_float(doc.get("vote_average")),
    )


def _composer_stats(composer_id: str, doc: dict[str, object]) -> ComposerStats:
    return ComposerStats(
        composer_id=composer_id,
        vote_count=_as_int(doc.get("vote_count")),
        vote_sum=_as_int(doc.get("vote_sum")),
        vote_average=_as_float(doc.get("vote_average")),
    )
