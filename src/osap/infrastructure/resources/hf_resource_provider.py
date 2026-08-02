from src.osap.domain.resource import Resource, ResourceKind, ResourceStatus
from src.osap.domain.value_objects import ProviderId, ResourceId
from src.osap.infrastructure.resources.resource_provider import IResourceProvider


class HuggingFaceResourceProvider(IResourceProvider):
    """Manages a Hugging Face dataset as a resource (e.g. PDMX).

    TODO(architecture): real install/update are not implemented yet; the large
    reported size is used to trigger user approval before any download.
    """

    def __init__(self, resource_id: str, name: str, dataset_path: str, size: int) -> None:
        self._resource_id = resource_id
        self._name = name
        self._path = dataset_path
        self._size = size
        self._installed = False

    @property
    def resource_id(self) -> str:
        return self._resource_id

    def install(self, index_only: bool = False) -> None:
        raise NotImplementedError("HuggingFace resource install is not implemented yet")

    def update(self) -> None:
        raise NotImplementedError("HuggingFace resource update is not implemented yet")

    def remove(self) -> None:
        self._installed = False

    def exists(self) -> bool:
        return self._installed

    def status(self) -> ResourceStatus:
        return ResourceStatus.INSTALLED if self._installed else ResourceStatus.NOT_INSTALLED

    def metadata(self) -> Resource:
        return Resource(
            resource_id=ResourceId(self._resource_id),
            name=self._name,
            kind=ResourceKind.DATASET,
            provider=ProviderId("huggingface"),
            status=self.status(),
            size=self._size,
            location=self._path,
            origin=self._path,
            license="public domain",
        )
