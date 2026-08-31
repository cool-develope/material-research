from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://material:material@localhost:5432/material"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_secure: bool = False
    minio_bucket: str = "material"

    workspace_root: Path = Path("/tmp/material-platform")

    discovery_version: str = "boundary-v1"
    pipeline_version: str = "process-v1"

    max_archive_depth: int = 5
    max_archive_files: int = 10_000
    max_expanded_bytes: int = 2 * 1024**3
    max_member_bytes: int = 512 * 1024**2
    max_compression_ratio: float = 200.0
    max_archive_timeout_seconds: int = 60


def get_settings() -> Settings:
    return Settings()
