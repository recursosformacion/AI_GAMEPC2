from enum import Enum


class DatasetStatus(Enum):
    """Availability state of a dataset managed by OSAP.

    The user never installs a dataset; OSAP manages it automatically.
    The state transitions from NOT_PRESENT → DOWNLOADING → READY (or STREAMING).
    """

    NOT_PRESENT = "not_present"
    DOWNLOADING = "downloading"
    STREAMING = "streaming"
    READY = "ready"
    ERROR = "error"
