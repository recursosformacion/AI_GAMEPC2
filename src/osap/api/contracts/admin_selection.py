"""Selección de representación, admin y modelo de búsqueda/intent."""

from .base import _Frozen


class RepresentationInput(_Frozen):
    id: str | None = None
    provider: str = ""
    format: str = ""
    url: str = ""
    title: str | None = None


class RepresentationSelectRequest(_Frozen):
    representations: list[RepresentationInput] = []


class RepresentationSelectionRead(_Frozen):
    work_id: str
    representations_known: int
    candidates_usable: int
    status: str
    message: str
    selected: dict[str, object] | None = None
    errors: list[str] = []


class AdminOverviewResponse(_Frozen):
    composers: dict[str, int] = {}
    source_suggestions_pending: int = 0
    source_suggestions: dict[str, int] = {}
    storage: dict[str, int] = {}


class UpsertProviderRequest(_Frozen):
    provider_id: str
    name: str
    base_url: str | None = None
    wired: bool = False
    config: dict[str, object] = {}
    description: dict[str, str] = {}
    endpoints: dict[str, object] = {}
    mapping: dict[str, object] = {}
    resources: dict[str, object] = {}
    transforms: dict[str, object] = {}


class SetProviderWiredRequest(_Frozen):
    wired: bool


class SetOpConfigRequest(_Frozen):
    key: str
    value: str


class SearchModelCriteria(_Frozen):
    key: str
    label: str


class SearchModelBlock(_Frozen):
    id: str
    label: str
    kind: str  # "text" | "multi" | "range" | "boolean"
    criteria: list[SearchModelCriteria] = []
    options: list[str] = []


class SearchModel(_Frozen):
    blocks: list[SearchModelBlock] = []


class IntentResponse(_Frozen):
    type: str  # composer | work | catalogue | collection | source
    label: str
    composer: str | None = None  # compositor detectado cuando la query mezcla título+compositor


class RegisterRequest(_Frozen):
    email: str
    password: str
    name: str | None = None


