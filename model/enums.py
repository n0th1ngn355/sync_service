"""
Application enums.

## Traceability
Infrastructure.
"""

from enum import Enum


class PaperStatusEnum(str, Enum):
    NEW = "NEW"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    COMPLETED = "COMPLETED"
    NOT_FOUND = "NOT_FOUND"
    FILTERED = "FILTERED"
    ERROR = "ERROR"


class FileTypeEnum(str, Enum):
    PDF = "PDF"
    TXT = "TXT"


class SyncStatusEnum(str, Enum):
    RUNNING = "RUNNING"
    OK = "OK"
    ERROR = "ERROR"


class SchedulerStatusEnum(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    OK = "OK"
    ERROR = "ERROR"
