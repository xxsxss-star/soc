import httpx
import pytest

from frontend.api_client import APIClient, APIClientError


def response(status: int, payload: dict, method: str, url: str) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request(method, url),
    )


def test_api_client_methods_use_expected_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, url: str, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/alerts"):
            return response(200, {"items": [{"alert_id": "ALT-001"}]}, method, url)
        if url.endswith("/runs"):
            return response(202, {"run_id": "RUN-1"}, method, url)
        if url.endswith("/human-decision"):
            return response(200, {"status": "completed"}, method, url)
        if url.endswith("/demo/reset"):
            return response(200, {"success": True}, method, url)
        if url.endswith("/health"):
            return response(200, {"status": "ok"}, method, url)
        return response(200, {"run_id": "RUN-1", "status": "queued"}, method, url)

    monkeypatch.setattr(httpx, "request", fake_request)
    client = APIClient("http://backend/api/v1/")

    assert client.list_alerts()[0]["alert_id"] == "ALT-001"
    assert client.create_run("ALT-001")["run_id"] == "RUN-1"
    assert client.get_run("RUN-1")["status"] == "queued"
    assert client.submit_human_decision("RUN-1", "continue_investigation")["status"] == "completed"
    assert client.reset_demo()["success"] is True
    assert client.health()["status"] == "ok"
    assert [call[0] for call in calls] == ["GET", "POST", "GET", "POST", "POST", "GET"]


def test_api_client_exposes_structured_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(method: str, url: str, **kwargs):
        return response(
            409,
            {"error": {"code": "ACTIVE_RUN_EXISTS", "message": "已有活动运行", "details": {}}},
            method,
            url,
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    with pytest.raises(APIClientError) as exc_info:
        APIClient("http://backend/api/v1").create_run("ALT-001")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ACTIVE_RUN_EXISTS"
    assert str(exc_info.value) == "已有活动运行"
