from __future__ import annotations

from typing import BinaryIO, cast

from minio import Minio
from minio.error import S3Error

from material_platform.config import Settings
from material_platform.infrastructure.object_store.paths import safe_object_key


class MinioObjectStore:
    def __init__(self, settings: Settings) -> None:
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket
        self.ensure_bucket()

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put(
        self,
        *,
        uri: str,
        data: BinaryIO,
        size: int,
        content_type: str | None = None,
    ) -> None:
        key = safe_object_key(uri)
        self._client.put_object(
            self._bucket,
            key,
            data,
            length=size,
            content_type=content_type or "application/octet-stream",
        )

    def open(self, uri: str) -> BinaryIO:
        key = safe_object_key(uri)
        return cast(BinaryIO, self._client.get_object(self._bucket, key))

    def exists(self, uri: str) -> bool:
        key = safe_object_key(uri)
        try:
            self._client.stat_object(self._bucket, key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise
        return True
