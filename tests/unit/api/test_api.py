from pathlib import Path

from fastapi.testclient import TestClient
from tests.unit.discovery.trees import SIMPLE_ZIP

from material_platform.api import create_app
from material_platform.application.local import ingest_and_process, sqlite_settings
from material_platform.application.runtime import Runtime
from material_platform.config import Settings


def _client(tmp_path: Path) -> TestClient:
    settings = sqlite_settings(Settings(_env_file=None), tmp_path / "data")
    ingest_and_process(SIMPLE_ZIP, settings, process=True)
    return TestClient(create_app(runtime=Runtime(settings)))


def test_health_ok(tmp_path: Path) -> None:
    settings = sqlite_settings(Settings(_env_file=None), tmp_path / "data")
    with TestClient(create_app(runtime=Runtime(settings))) as client:
        response = client.get(
            "/health", headers={"Origin": "http://localhost:5173"}
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers.get("access-control-allow-origin") == (
        "http://localhost:5173"
    )


def test_search_returns_materials(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/search", json={"query": "handle_request"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "handle_request"
    assert body["page"] == 1
    assert body["page_size"] == 10
    results = body["results"]
    assert results
    assert results[0]["root_path"]
    assert results[0]["material_type"]
    assert results[0]["material_id"]
    assert "citation" not in results[0]
    assert body["trace_url"] is None


def test_search_filters_material_type(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        project = client.post(
            "/search",
            json={"query": "handle_request", "material_type": "project"},
        )
        document = client.post(
            "/search",
            json={"query": "handle_request", "material_type": "document"},
        )
    assert project.status_code == 200
    assert project.json()["results"]
    assert all(item["material_type"] == "project" for item in project.json()["results"])
    assert document.status_code == 200
    assert all(
        item["material_type"] == "document" for item in document.json()["results"]
    )


def test_search_paginates(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        first = client.post(
            "/search", json={"query": "handle_request", "page": 1, "page_size": 1}
        )
        second = client.post(
            "/search", json={"query": "handle_request", "page": 2, "page_size": 1}
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["has_more"] is True
    assert first.json()["results"]
    assert second.json()["results"]
    assert (
        first.json()["results"][0]["material_id"]
        != second.json()["results"][0]["material_id"]
    )


def test_search_rejects_empty_and_unknown_type(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        empty = client.post("/search", json={"query": "   "})
        unknown = client.post(
            "/search", json={"query": "handle_request", "material_type": "nope"}
        )
        too_many = client.post(
            "/search", json={"query": "handle_request", "page_size": 50}
        )
    assert empty.status_code == 422
    assert unknown.status_code == 422
    assert too_many.status_code == 422


def test_chat_returns_cited_report(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/chat", json={"query": "handle_request", "mode": "quick"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "quick"
    assert body["text"]
    assert body["citations"]
    assert any("src/api.py" in item["citation"] for item in body["citations"])
    assert body["thread_id"]


def test_chat_continues_thread(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        first = client.post("/chat", json={"query": "handle_request", "mode": "quick"})
        thread_id = first.json()["thread_id"]
        second = client.post(
            "/chat",
            json={
                "query": "where is it defined",
                "mode": "quick",
                "thread_id": thread_id,
            },
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["thread_id"] == thread_id
    assert second.json()["text"]


def test_chat_history_returns_full_transcript(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        first = client.post("/chat", json={"query": "handle_request", "mode": "quick"})
        thread_id = first.json()["thread_id"]
        client.post(
            "/chat",
            json={
                "query": "where is it defined",
                "mode": "quick",
                "thread_id": thread_id,
            },
        )
        history = client.get(f"/chat/{thread_id}")
        missing = client.get("/chat/does-not-exist")
    assert first.status_code == 200
    assert history.status_code == 200
    body = history.json()
    assert body["thread_id"] == thread_id
    messages = body["messages"]
    assert [item["role"] for item in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0]["content"] == "handle_request"
    assert messages[2]["content"] == "where is it defined"
    assert first.json()["text"] in messages[1]["content"]
    assert missing.status_code == 404
