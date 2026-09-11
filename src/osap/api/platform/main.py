"""Use cases del OSAP Platform API (módulo principal del paquete, F5.4)."""

import os
import threading
from typing import TYPE_CHECKING

from src.osap.api.platform import _support as _support
from src.osap.api.platform._support import (
    KnowledgeStore,
    SessionSources,
    SourceCatalog,
)
from src.osap.api.platform.composers import ComposersMixin
from src.osap.api.platform.core import PlatformApiCore
from src.osap.api.platform.corrections import CorrectionsMixin
from src.osap.api.platform.jobs import JobsMixin
from src.osap.api.platform.knowledge import KnowledgeMixin
from src.osap.api.platform.providers import ProvidersMixin
from src.osap.api.platform.resolution import ResolutionMixin
from src.osap.api.platform.search import SearchMixin
from src.osap.api.platform.sources import SourcesMixin
from src.osap.api.platform.system import SystemMixin
from src.osap.api.platform.votes_users import VotesUsersMixin
from src.osap.bootstrap.container import Container
from src.osap.infrastructure.state.op_store import build_op_store
from src.osap.infrastructure.state.resolution_store import build_resolution_store

if TYPE_CHECKING:
    from src.osap.api.contracts import JobResponse, RepresentationInfo, SearchResponse

VERSION = "3.1"


















class PlatformApi(
    SearchMixin,
    ResolutionMixin,
    ComposersMixin,
    VotesUsersMixin,
    ProvidersMixin,
    SourcesMixin,
    CorrectionsMixin,
    KnowledgeMixin,
    SystemMixin,
    JobsMixin,
    PlatformApiCore,
):
    """Use cases of the OSAP Platform API, backed by existing application services."""

    def __init__(
        self,
        container: Container,
        knowledge: KnowledgeStore | None = None,
        catalog: SourceCatalog | None = None,
    ) -> None:
        self._container = container
        self._knowledge = knowledge or KnowledgeStore()
        self._catalog = catalog or SourceCatalog()
        self._sessions = SessionSources()
        self._searches: dict[str, SearchResponse] = {}
        self._search_cache: dict[str, SearchResponse] = {}
        self._work_rep_cache: dict[str, list[RepresentationInfo]] = {}
        self._work_rep_order: list[str] = []
        self._jobs: dict[str, JobResponse] = {}
        self._representations: dict[str, dict[str, object]] = {}
        self._job_counter = 0
        self._oidc_pending: dict[str, dict[str, object]] = {}
        self._oidc_pending_path = os.environ.get("OSAP_OIDC_STATE_FILE") or ""
        self._oidc_pending_lock = threading.Lock()
        if self._oidc_pending_path:
            self._oidc_pending = self._load_oidc_pending()
        self._suggestion_counter = 0
        self._store = build_op_store(**(self._container.op_store_config() or {}))
        self._resolution_store = build_resolution_store(**(self._container.op_store_config() or {}))
        self._acquisition = self._build_acquisition_service()
        highest = 0
        for item in self._store.list_suggestions():
            sid = str(item.get("id") or "")
            if sid.startswith("sug-"):
                try:
                    highest = max(highest, int(sid[4:]))
                except ValueError:
                    continue
        self._suggestion_counter = highest + 1

    # --- search -------------------------------------------------------------

