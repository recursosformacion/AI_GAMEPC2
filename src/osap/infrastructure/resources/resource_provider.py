from abc import ABC, abstractmethod

from src.osap.domain.resource import Resource, ResourceStatus


class IResourceProvider(ABC):
    """Manages the lifecycle of a concrete external resource (install/update/remove).

    Resource providers never answer musical questions; they only manage
    installation. The domain never knows the concrete technology behind a
    resource.
    """

    @property
    @abstractmethod
    def resource_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def install(self, index_only: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> ResourceStatus:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> Resource:
        raise NotImplementedError
