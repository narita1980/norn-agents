from fastapi.testclient import TestClient


def test_post_message_creates_thread(client: TestClient) -> None:
    response = client.post("/chat/messages", json={"content": "Hello Norn!"})
    assert response.status_code == 201
    body = response.json()
    assert body["thread_id"]
    assert body["message_id"]
    assert "Phase 2" in body["reply"]


def test_post_message_reuses_thread_id(client: TestClient) -> None:
    first = client.post("/chat/messages", json={"content": "first"}).json()
    second = client.post(
        "/chat/messages",
        json={"thread_id": first["thread_id"], "content": "second"},
    ).json()
    assert second["thread_id"] == first["thread_id"]


def test_get_thread_returns_messages(client: TestClient) -> None:
    post = client.post("/chat/messages", json={"content": "ping"}).json()
    response = client.get(f"/chat/threads/{post['thread_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == post["thread_id"]
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"


def test_get_unknown_thread_returns_404(client: TestClient) -> None:
    response = client.get("/chat/threads/does-not-exist")
    assert response.status_code == 404


def test_empty_content_rejected(client: TestClient) -> None:
    response = client.post("/chat/messages", json={"content": ""})
    assert response.status_code == 422
