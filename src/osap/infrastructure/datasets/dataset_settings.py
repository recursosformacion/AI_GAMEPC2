from dataclasses import dataclass

from src.osap.domain.dataset_mode import DatasetMode


@dataclass(frozen=True)
class DatasetSettings:
    """Runtime configuration for dataset installation and querying."""

    cache_dir: str | None = None
    mode: DatasetMode = DatasetMode.AUTO
    num_proc: int | None = None
    offline: bool = False
    download_mode: str = "reuse_dataset_if_exists"
    max_disk_usage_bytes: int | None = None
    auto_update: bool = False
