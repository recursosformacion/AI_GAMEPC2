from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .value_objects import ProviderId, ResourceId


class ResourceKind(Enum):
    DATASET = "dataset"
    CATALOG = "catalog"
    MODEL = "model"
    CACHE = "cache"
    KNOWLEDGE_BASE = "knowledge_base"
    DICTIONARY = "dictionary"


class ResourceStatus(Enum):
    NOT_INSTALLED = "not_installed"
    INDEX_ONLY = "index_only"
    PARTIAL = "partial"
    INSTALLED = "installed"
    UPDATING = "updating"
    ERROR = "error"


@dataclass(frozen=True)
class Resource:
    """Any external resource OSAP may need (dataset, catalog, model, cache, ...)."""

    resource_id: ResourceId
    name: str
    kind: ResourceKind
    provider: ProviderId
    status: ResourceStatus = ResourceStatus.NOT_INSTALLED
    version: str | None = None
    size: int | None = None
    location: str | None = None
    license: str | None = None
    origin: str | None = None
    last_update: datetime | None = None
    update_policy: str | None = None
