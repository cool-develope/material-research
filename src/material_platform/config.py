import os
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


def in_pytest() -> bool:
    return "PYTEST_VERSION" in os.environ


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
    max_extract_bytes: int = 8 * 1024 * 1024
    max_units_per_material: int = 20
    chunk_tokens: int = 512
    chunk_overlap_tokens: int = 64
    retry_delay_seconds: int = 2

    qdrant_url: str | None = None
    qdrant_path: Path | None = None
    qdrant_collection: str = "research"
    embedder: str = "fake"
    bge_model: str = "BAAI/bge-m3"
    bge_reranker: str = "BAAI/bge-reranker-v2-m3"
    reranker: str = "off"

    analyzer: str = "deterministic"
    llm_base_url: str | None = None
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.1"
    llm_timeout_seconds: int = 120
    analysis_direct_tokens: int = 20_000
    analysis_leaf_tokens: int = 10_000
    analysis_reduce_fanin: int = 8
    analysis_deep_files: int = 20

    agent_mode: str = "standard"

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if in_pytest():
            return init_settings, env_settings, file_secret_settings
        return init_settings, env_settings, dotenv_settings, file_secret_settings


def get_settings() -> Settings:
    return Settings()
