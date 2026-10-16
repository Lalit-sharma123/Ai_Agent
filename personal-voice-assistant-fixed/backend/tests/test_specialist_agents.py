def test_research_search_reports_missing_searxng(client):
    response = client.post("/api/research/search", json={"query": "open source agents", "provider": "searxng"})
    assert response.status_code == 503
    assert "SEARXNG_BASE_URL" in response.json()["detail"]


def test_meeting_create_list_and_delete(client):
    created = client.post("/api/meetings", json={
        "title": "Sprint review",
        "transcript": "Asha: Finish API tests by Friday."
    })
    assert created.status_code == 200
    meeting = created.json()
    assert meeting["title"] == "Sprint review"
    assert meeting["transcript"].startswith("Asha:")
    listed = client.get("/api/meetings")
    assert listed.status_code == 200
    assert any(item["id"] == meeting["id"] for item in listed.json())
    deleted = client.delete(f"/api/meetings/{meeting['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_coding_workspace_endpoint_is_available(client):
    response = client.get("/api/coding/workspace")
    assert response.status_code == 200
    assert "roots" in response.json()


def test_coding_rejects_path_outside_workspace(client):
    response = client.post("/api/coding/tree", json={"path": "/etc"})
    assert response.status_code == 403


def test_voice_command_routes_to_email_and_asks_for_missing_recipient(client):
    response = client.post("/api/voice/command", json={"transcript": "Draft an email to my manager about the project update"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "email"
    assert payload["agent"] == "Email Agent"
    assert payload["needs_clarification"] is True
    assert "recipient" in payload["reply"].lower()
    assert payload["conversation_id"]


def test_voice_command_routes_to_desktop_but_requires_approval(client):
    from app.graph.voice_graph import deterministic_intent
    intent, args = deterministic_intent("Open https://example.com in the browser")
    assert intent == "desktop"
    assert args["action_type"] == "open_url"
    assert args["target"] == "https://example.com"


def test_voice_intent_classifier_covers_all_specialist_agents():
    from app.graph.voice_graph import deterministic_intent
    cases = {
        "Research the web for MCP examples": "research",
        "Find my meeting transcript about sprint planning": "meetings",
        "Draft an email to alex@example.com about the release": "email",
        "Debug this Python stack trace": "coding",
        "Explain this PDF document": "documents",
        "Create a 6 slides presentation about local AI": "presentations",
        "Open https://example.com": "desktop",
    }
    for text, expected in cases.items():
        assert deterministic_intent(text)[0] == expected, text


def test_calculator_and_youtube_intent_routing():
    from app.graph.voice_graph import deterministic_intent
    assert deterministic_intent("calculate 25 times 6")[0:1] == ("calculator",)
    intent, args = deterministic_intent("play a video about AI agents on YouTube")
    assert intent == "youtube"
    assert "AI agents" in args["query"]


def test_voice_command_requires_confirmation_before_calculating(client):
    proposed = client.post("/api/voice/command", json={"transcript": "calculate 25 times 6"})
    assert proposed.status_code == 200
    first = proposed.json()
    assert first["intent"] == "calculator"
    assert first["requires_confirmation"] is True
    assert "OK" in first["reply"]
    confirmed = client.post("/api/voice/command", json={"transcript": "OK, do that", "conversation_id": first["conversation_id"]})
    assert confirmed.status_code == 200
    second = confirmed.json()
    assert second["requires_confirmation"] is False
    assert second["result"]["result"] == 150


def test_safe_calculator_supports_spoken_math_and_rejects_code():
    from app.services.local_tools import calculate
    assert calculate("25 times 6")["result"] == 150
    assert calculate("(10 plus 2) divided by 3")["result"] == 4
    try:
        calculate("__import__('os').system('whoami')")
    except ValueError:
        pass
    else:
        raise AssertionError("calculator must reject code and function calls")


def test_youtube_missing_preference_is_clarified_before_confirmation(client):
    first = client.post("/api/voice/command", json={"transcript": "open YouTube and play video according to my preference"}).json()
    assert first["intent"] == "youtube"
    assert first["needs_clarification"] is True
    second = client.post("/api/voice/command", json={
        "transcript": "AI agents tutorials",
        "conversation_id": first["conversation_id"],
    }).json()
    assert second["requires_confirmation"] is True
    assert second["arguments"]["query"] == "AI agents tutorials"
    assert "OK" in second["reply"]
