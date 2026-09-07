from app.core.config import settings


def test_health_allows_inline_mode_without_redis(client, monkeypatch):
    monkeypatch.setattr(settings, "task_queue_mode", "inline")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["database"] == "ok"


def test_health_requires_redis_for_persistent_queue(client, monkeypatch):
    monkeypatch.setattr(settings, "task_queue_mode", "redis")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["redis"] == "down"
