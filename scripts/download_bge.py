"""Download BGE-M3 and the v2-m3 reranker into the Hugging Face cache."""

from __future__ import annotations

MODELS = (
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
)


def main() -> int:
    from huggingface_hub import snapshot_download

    for name in MODELS:
        print(f"downloading {name} ...", flush=True)
        path = snapshot_download(repo_id=name)
        print(f"  cached at {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
