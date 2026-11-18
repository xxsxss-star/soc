from __future__ import annotations

from typing import Any

import httpx


class APIClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str = "") -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class APIClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise APIClientError(f"无法连接后端：{exc}") from exc
        if response.is_error:
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            raise APIClientError(
                error.get("message", f"后端返回 HTTP {response.status_code}"),
                status_code=response.status_code,
                code=error.get("code", "HTTP_ERROR"),
            )
        return response.json()

    def list_alerts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/alerts")["items"]

    def create_run(self, alert_id: str) -> dict[str, Any]:
        return self._request("POST", "/runs", json={"alert_id": alert_id})

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/runs/{run_id}")

    def submit_human_decision(
        self, run_id: str, decision: str, comment: str = ""
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/runs/{run_id}/human-decision",
            json={"decision": decision, "comment": comment},
        )

    def reset_demo(self) -> dict[str, Any]:
        return self._request("POST", "/demo/reset")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")
