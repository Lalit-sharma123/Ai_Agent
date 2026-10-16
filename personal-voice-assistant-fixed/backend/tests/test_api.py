from app.core.model_adapters import ModelError

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_root_endpoint(client):
    assert client.get("/").json()["docs"] == "/docs"

def test_empty_chat_rejected(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422

def test_unconfigured_model_returns_helpful_error(client):
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]

def test_conversation_not_found(client):
    response = client.get("/api/conversations/not-real/messages")
    assert response.status_code == 404


def test_chat_persists_user_and_assistant_messages(client, monkeypatch):
    async def fake_respond(user_text, history, provider=None):
        return {"content": f"Echo: {user_text}", "provider": "qwen", "model": "mock-model"}

    monkeypatch.setattr(client.app.state.orchestrator, "respond", fake_respond)
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["assistant"]["content"] == "Echo: hello"
    assert body["conversation_id"]
    messages = client.get(f"/api/conversations/{body['conversation_id']}/messages")
    assert messages.status_code == 200
    assert [m["role"] for m in messages.json()] == ["user", "assistant"]
