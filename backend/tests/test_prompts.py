"""Tests for prompt version registry."""


def _prompt(client, name="my_prompt", version="v1"):
    r = client.post("/prompts", json={
        "prompt_name": name,
        "version": version,
        "prompt_text": "Answer concisely: {query}",
        "is_active": True,
    })
    assert r.status_code == 201
    return r.json()


def test_create_prompt(client):
    p = _prompt(client)
    assert p["prompt_name"] == "my_prompt"
    assert p["version"] == "v1"
    assert p["is_active"] is True


def test_list_prompts(client):
    _prompt(client, "p1", "v1")
    _prompt(client, "p2", "v1")
    r = client.get("/prompts")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_prompt(client):
    p = _prompt(client)
    r = client.get(f"/prompts/{p['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == p["id"]


def test_get_prompt_not_found(client):
    r = client.get("/prompts/nonexistent")
    assert r.status_code == 404


def test_prompt_versions(client):
    _prompt(client, "rag_prompt", "v1")
    _prompt(client, "rag_prompt", "v2")
    r = client.get("/prompts")
    names = [p["prompt_name"] for p in r.json()]
    assert names.count("rag_prompt") == 2
