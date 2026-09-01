from __future__ import annotations

from threading import Lock

from qdrant_client import QdrantClient

from material_platform.config import Settings

_PATH_CLIENTS: dict[str, QdrantClient] = {}
_LOCK = Lock()


def make_qdrant_client(settings: Settings) -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url)
    path = settings.qdrant_path
    if path is not None and str(path) == ":memory:":
        return QdrantClient(":memory:")
    root = (path or (settings.workspace_root / "qdrant")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    key = str(root)
    with _LOCK:
        client = _PATH_CLIENTS.get(key)
        if client is None:
            client = QdrantClient(path=key)
            _PATH_CLIENTS[key] = client
        return client
