from fastapi import APIRouter, Request

from backend.models.api import DemoResetResponse, HealthResponse


router = APIRouter(tags=["demo"])


@router.post("/demo/reset", response_model=DemoResetResponse)
def reset_demo(request: Request) -> DemoResetResponse:
    alerts_reset, runs_removed = request.app.state.run_service.reset()
    return DemoResetResponse(
        success=True,
        message="Demo状态已恢复",
        alerts_reset=alerts_reset,
        runs_removed=runs_removed,
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    service = request.app.state.run_service
    return HealthResponse(
        ai_mode=settings.ai_mode,
        data_loaded=service.data_store is not None,
        alert_count=len(service.data_store.list_alerts()),
    )
