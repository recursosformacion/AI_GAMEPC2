from dataclasses import dataclass


@dataclass(frozen=True)
class Configuration:
    confidence_threshold: float = 0.8
    max_processing_time: float = 300.0
    default_quality_level: str = "full_notation"
    default_output_format: str = "musicxml"
    default_library: str | None = None
    connectivity_available: bool = True
    library_root: str = "osap_library"
    imslp_base_url: str = "https://api.imslp.org"
    pdmx_csv_url: str = "https://zenodo.org/records/15571083/files/PDMX.csv?download=1"
    pdmx_index_path: str = "pdmx_index.db"
    pdmx_download_base: str | None = None
    resource_auto_install: bool = True
    resource_auto_install_size_threshold: int | None = 1_000_000_000  # 1 GB
    github_token: str | None = None
    github_timeout: int = 20
    github_retries: int = 3
    github_cache: bool = True
    openscore_repos: tuple[str, ...] = ("OpenScore/Lieder",)
    imslp_verify_ssl: bool = True
    datasets_cache_dir: str | None = None
    datasets_mode: str = "auto"
    datasets_num_proc: int | None = None
    datasets_download_mode: str = "reuse_dataset_if_exists"
    datasets_max_disk_usage: int | None = None
    datasets_auto_update: bool = False
    credentials_path: str = "osap_credentials.db"
    credentials_key: str | None = None
