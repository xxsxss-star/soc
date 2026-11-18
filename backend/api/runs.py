from fastapi import APIRouter, Request, status

from backend.api.errors import APIError
from backend.models.api import (
    CreateRunRequest,
    CreateRunResponse,
    HumanDecisionRequest,
    HumanDecisionResponse,
    RunResponse,
)
from backend.services.run_service import (
    ActiveRunExistsError,
    AlertNotFoundError,
    InvalidRunStateError,
    RunNotFoundError,
)


router = APIRouter(tags=["runs"])


def _run_response(record) -> RunResponse:
    state = record.state
    return RunResponse(
        run_id=record.run_id,
        alert_id=record.alert_id,
        status=record.status,
        analysis_mode=record.analysis_mode,
        timeline=state.get("timeline", []),
        evidence_package=state.get("evidence_package"),
        rule_result=state.get("rule_result"),
        ai_result=state.get("ai_result"),
        decision=state.get("decision"),
        human_decision=state.get("human_decision"),
    )


@router.post("/runs", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_run(payload: CreateRunRequest, request: Request) -> CreateRunResponse:
    service = request.app.state.run_service
    try:
        record = service.create_run(payload.alert_id)
    except AlertNotFoundError as exc:
        raise APIError(
            status_code=404,
            code="ALERT_NOT_FOUND",
            message=f"未找到告警 {payload.alert_id}",
            details={"alert_id": payload.alert_id},
        ) from exc
    except ActiveRunExistsError as exc:
        raise APIError(
            status_code=409,
            code="ACTIVE_RUN_EXISTS",
            message=f"告警 {payload.alert_id} 已存在未完成运行",
            details={"alert_id": payload.alert_id, "run_id": exc.record.run_id},
        ) from exc
    return CreateRunResponse(
        run_id=record.run_id,
        alert_id=record.alert_id,
        poll_url=f"/api/v1/runs/{record.run_id}",
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, request: Request) -> RunResponse:
    try:
        return _run_response(request.app.state.run_service.get_run(run_id))
    except RunNotFoundError as exc:
        raise APIError(
            status_code=404,
            code="RUN_NOT_FOUND",
            message=f"未找到运行 {run_id}",
            details={"run_id": run_id},
        ) from exc


@router.post("/runs/{run_id}/human-decision", response_model=HumanDecisionResponse)
def submit_human_decision(
    run_id: str,
    payload: HumanDecisionRequest,
    request: Request,
) -> HumanDecisionResponse:
    try:
        _record, human_decision = request.app.state.run_service.submit_human_decision(
            run_id, payload.decision, payload.comment
        )
    except RunNotFoundError as exc:
        raise APIError(
            status_code=404,
            code="RUN_NOT_FOUND",
            message=f"未找到运行 {run_id}",
            details={"run_id": run_id},
        ) from exc
    except InvalidRunStateError as exc:
        raise APIError(
            status_code=409,
            code="INVALID_RUN_STATE",
            message="只有 waiting_human 状态允许提交人工决定",
            details={"run_id": run_id, "reason": str(exc)},
        ) from exc
    return HumanDecisionResponse(run_id=run_id, human_decision=human_decision)
