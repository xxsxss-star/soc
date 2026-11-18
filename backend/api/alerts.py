from fastapi import APIRouter, Request

from backend.models.api import AlertListItem, AlertListResponse


router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(request: Request) -> AlertListResponse:
    service = request.app.state.run_service
    return AlertListResponse(
        items=[
            AlertListItem(
                alert_id=alert.alert_id,
                alert_name=alert.alert_name,
                severity=alert.severity,
                source=alert.source,
                hostname=alert.hostname,
                dst_ip=alert.dst_ip,
                demo_scenario=alert.demo_scenario,
                status=status,
            )
            for alert, status in service.list_alerts_with_status()
        ]
    )
