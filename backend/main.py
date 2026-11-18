from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.alerts import router as alerts_router
from backend.api.demo import router as demo_router
from backend.api.errors import APIError
from backend.api.runs import router as runs_router
from backend.config import Settings, get_settings
from backend.models.api import ErrorDetail, ErrorResponse
from backend.services.ai_analyzer import create_ai_analyzer
from backend.services.data_store import JsonDataStore
from backend.services.run_service import RunService
from backend.workflow.graph import AlertWorkflow


def create_app(settings: Settings | None = None, run_service: RunService | None = None) -> FastAPI:
    selected = settings or get_settings()
    if run_service is None:
        data_store = JsonDataStore(selected.data_dir)
        workflow = AlertWorkflow(
            data_store=data_store,
            ai_analyzer=create_ai_analyzer(selected),
            settings=selected,
        )
        run_service = RunService(data_store=data_store, workflow=workflow)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        run_service.shutdown()

    application = FastAPI(title="AlertLens API", version="0.1.0", lifespan=lifespan)
    application.state.settings = selected
    application.state.run_service = run_service

    @application.exception_handler(APIError)
    async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details)
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(
                code="REQUEST_VALIDATION_ERROR",
                message="请求参数校验失败",
                details={"errors": exc.errors()},
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                details={},
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    application.include_router(alerts_router, prefix="/api/v1")
    application.include_router(runs_router, prefix="/api/v1")
    application.include_router(demo_router, prefix="/api/v1")
    return application


app = create_app()
