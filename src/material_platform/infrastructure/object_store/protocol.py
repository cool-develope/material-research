from typing import BinaryIO, Protocol


class UnsafeStoragePathError(ValueError):
    pass


class ObjectStore(Protocol):
    def put(
        self,
        *,
        uri: str,
        data: BinaryIO,
        size: int,
        content_type: str | None = None,
    ) -> None: ...

    def open(self, uri: str) -> BinaryIO: ...

    def exists(self, uri: str) -> bool: ...
