"""Feature-flag behavior tests for global chat routes."""
import copy

from app.config import get_config


def test_chat_status_includes_enabled_flag(client):
    response = client.get("/api/chat/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "enabled" in data
    assert "configured" in data


def test_chat_endpoint_blocked_when_feature_disabled(client):
    runtime = get_config()
    original = copy.deepcopy(runtime.get_all_features())
    try:
        runtime.set_feature_enabled("chat_enabled", False)
        response = client.post("/api/chat", json={"message": "hello"})
        assert response.status_code == 403
        data = response.get_json()
        assert data["success"] is False
    finally:
        for name, cfg in original.items():
            runtime.set_feature_enabled(name, cfg.get("enabled", False))
