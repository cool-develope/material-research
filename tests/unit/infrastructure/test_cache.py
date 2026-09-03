from material_platform.infrastructure.cache import QueryCache, make_query_cache


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    def ping(self) -> bool:
        return True


def test_query_cache_roundtrip_memory() -> None:
    cache = QueryCache()
    cache.set_json("mp:emb:x", {"dense": [1.0]})
    assert cache.get_json("mp:emb:x") == {"dense": [1.0]}
    assert cache.get_json("missing") is None


def test_query_cache_reads_through_redis() -> None:
    redis = _FakeRedis()
    writer = QueryCache(redis)
    writer.set_json("k", {"v": 2})
    reader = QueryCache(redis)
    assert reader.get_json("k") == {"v": 2}


def test_make_query_cache_without_url_stays_in_memory() -> None:
    cache = make_query_cache(None)
    cache.set_json("k", 1)
    assert cache.get_json("k") == 1
