def test_research_browse_rejects_private_or_local_urls(client):
    response = client.post("/api/research/browse", json={"url": "http://127.0.0.1:8000/health"})
    assert response.status_code == 400


def test_research_synthesis_requires_sources(client):
    response = client.post("/api/research/synthesize", json={"query": "compare products", "sources": []})
    assert response.status_code == 422


def test_meeting_search_finds_saved_transcript(client):
    created = client.post("/api/meetings", json={"title": "Planning", "transcript": "Mira will send the roadmap"})
    assert created.status_code == 200
    response = client.get("/api/meetings/search", params={"q": "roadmap"})
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_desktop_actions_require_approval(client):
    proposed = client.post("/api/desktop/actions", json={"action_type": "open_url", "target": "https://example.com"})
    assert proposed.status_code == 200
    action = proposed.json()
    assert action["status"] == "pending_approval"
    rejected = client.post(f"/api/desktop/actions/{action['id']}/approve", json={"approved": False})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_desktop_rejects_non_http_url(client):
    response = client.post("/api/desktop/actions", json={"action_type": "open_url", "target": "file:///etc/passwd"})
    assert response.status_code == 400


def test_document_list_and_email_draft_not_found(client):
    assert client.get("/api/documents").status_code == 200
    response = client.post("/api/email/drafts/not-real/send", json={"approved": True})
    assert response.status_code == 404


def test_presentation_validates_slide_count(client):
    response = client.post("/api/presentations/generate", json={"topic": "Test", "slide_count": 50})
    assert response.status_code == 422


def test_deleting_indexed_document_does_not_delete_original(client, tmp_path):
    import json
    from pathlib import Path
    documents_dir = tmp_path / "docs"
    documents_dir.mkdir()
    original = tmp_path / "important.txt"
    original.write_text("user-owned source file", encoding="utf-8")
    client.app.state.settings.documents_dir = str(documents_dir)
    document_id = "safe-delete-test"
    meta = {"id": document_id, "name": original.name, "extension": ".txt",
            "path": str(original), "text": original.read_text(), "source": "approved_workspace"}
    (documents_dir / f"{document_id}.json").write_text(json.dumps(meta), encoding="utf-8")
    response = client.delete(f"/api/documents/{document_id}")
    assert response.status_code == 200
    assert original.exists()
