import pytest

from src.osap.bootstrap.configuration import Configuration, ConfigurationError
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire


def test_development_requires_explicit_database_configuration() -> None:
    config = Configuration(deployment="development")

    with pytest.raises(ConfigurationError, match="osap_api_db_host"):
        wire(Container(), configuration=config)
