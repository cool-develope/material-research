from __future__ import annotations

import hashlib
import json
import time
from typing import Any

_TTL = 3600
_MEM_MAX = 256


class QueryCache:
    def __init__(self, redis_client: object | None = None, ttl: int = _TTL) -> None:
        self._redis = redis_client
        self._ttl = ttl
        self._mem: dict[str, tuple[float, str]] = {}

    def embed_key(self, model: str, query: str) -> str:
        return f"mp:emb:{model}:{_digest(query)}"

    def window_key(self, collection: str, model: str, query: str, kind: str) -> str:
        return f"mp:serp:{collection}:{model}:{kind}:{_digest(query)}"

    def get_json(self, key: str) -> Any | None:
        now = time.monotonic()
        cached = self._mem.get(key)
        if cached is not None and cached[0] > now:
            return json.loads(cached[1])
        if cached is not None:
            self._mem.pop(key, None)
        client = self._redis
        if client is None:
            return None
        try:
            blob = client.get(key)
        except Exception:
            return None
        if not isinstance(blob, str) or not blob:
            return None
        self._remember(key, blob)
        return json.loads(blob)

    def set_json(self, key: str, value: object) -> None:
        blob = json.dumps(value)
        self._remember(key, blob)
        client = self._redis
        if client is None:
            return
        try:
            client.set(key, blob, ex=self._ttl)
        except Exception:
            return

    def _remember(self, key: str, blob: str) -> None:
        self._mem[key] = (time.monotonic() + self._ttl, blob)
        if len(self._mem) > _MEM_MAX:
            oldest = min(self._mem, key=lambda item: self._mem[item][0])
            self._mem.pop(oldest, None)


def make_query_cache(redis_url: str | None) -> QueryCache:
    if not redis_url:
        return QueryCache()
    try:
        import redis
    except ImportError:
        return QueryCache()
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except Exception:
        return QueryCache()
    return QueryCache(client)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
