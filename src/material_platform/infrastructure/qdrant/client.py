from __future__ import annotations

import atexit
from threading import Lock

from qdrant_client import QdrantClient

from material_platform.config import Settings

_PATH_CLIENTS: dict[str, QdrantClient] = {}
_LOCK = Lock()
_ATEXIT = False


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
            _register_atexit()
        return client


def close_path_clients() -> None:
    with _LOCK:
        clients = list(_PATH_CLIENTS.values())
        _PATH_CLIENTS.clear()
    for client in clients:
        client.close()


def _register_atexit() -> None:
    global _ATEXIT
    if _ATEXIT:
        return
    atexit.register(close_path_clients)
    _ATEXIT = True
