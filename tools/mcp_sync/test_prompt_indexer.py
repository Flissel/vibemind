import prompt_indexer


ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "tool": "docker", "agent_name": "tool-docker",
    "description": "Run and manage docker containers",
    "trigger": "deploy|container|image",
    "prompt_template": "Start a container from {image} named {name}",
    "slots": {"image": {"source": "kg", "required": True}},
}


def test_embedding_text_combines_desc_trigger_tool():
    txt = prompt_indexer.embedding_text(ROW)
    assert "Run and manage docker containers" in txt
    assert "deploy|container|image" in txt
    assert "docker" in txt


def test_point_id_is_stable_per_tool():
    a = prompt_indexer.point_id_for(ROW)
    b = prompt_indexer.point_id_for({**ROW, "description": "changed"})
    assert a == b
    assert a != prompt_indexer.point_id_for({**ROW, "tool": "redis"})


def test_payload_carries_supabase_id_and_visibility():
    p = prompt_indexer.payload_for({**ROW, "visibility": ["brain", "*"]})
    assert p["supabase_id"] == ROW["id"]
    assert p["tool"] == "docker"
    assert p["visibility"] == ["brain", "*"]
