from enum import StrEnum


class SourceType(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    ARCHIVE = "archive"


class SourceStatus(StrEnum):
    REGISTERED = "registered"
    DISCOVERING = "discovering"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    ARCHIVE = "archive"


class DiscoveryRole(StrEnum):
    UNKNOWN = "unknown"
    CONTAINER = "container"
    MATERIAL = "material"
    IGNORED = "ignored"


class DiscoveryRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MaterialType(StrEnum):
    DOCUMENT = "document"
    PROJECT = "project"
    DATASET = "dataset"
    CODE = "code"
    IMAGE = "image"
    PRESENTATION = "presentation"
    SPREADSHEET = "spreadsheet"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class MaterialStatus(StrEnum):
    DISCOVERED = "discovered"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    ANALYZED = "analyzed"
    INDEXED = "indexed"
    READY = "ready"
    FAILED = "failed"


class ProcessingRunStatus(StrEnum):
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
