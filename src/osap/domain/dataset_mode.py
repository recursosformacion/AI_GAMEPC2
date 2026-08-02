from enum import Enum


class DatasetMode(Enum):
    """How OSAP handles a dataset that is not yet cached.

    AUTO:     try cache first; fall back to streaming if available.
    CACHE:    only use the dataset if fully cached; auto-download.
    STREAMING: use streaming; never download the full dataset.
    """

    AUTO = "auto"
    CACHE = "cache"
    STREAMING = "streaming"
