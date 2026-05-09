import json
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import trace_id_ctx_var
from app.db.session import SessionLocal
from app.models.scale_foundation import APIRequestLog

logger = logging.getLogger(__name__)


def install_api_contract_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        payload = {
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "details": None,
            "trace_id": trace_id,
        }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        payload = {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
            "trace_id": trace_id,
        }
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        logger.exception("Unhandled exception. trace_id=%s", trace_id)
        payload = {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Unexpected server error",
            "details": None,
            "trace_id": trace_id,
        }
        return JSONResponse(status_code=500, content=payload)


def install_observability_middleware(app: FastAPI, slow_ms_threshold: int = 800) -> None:
    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        token = trace_id_ctx_var.set(trace_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if elapsed_ms > slow_ms_threshold:
                logger.warning(
                    "Slow API request detected: path=%s method=%s latency_ms=%s trace_id=%s",
                    request.url.path,
                    request.method,
                    elapsed_ms,
                    trace_id,
                )

            user_id = getattr(getattr(request.state, "current_user", None), "id", None)
            log_payload = {
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "latency_ms": elapsed_ms,
                "user_id": str(user_id) if user_id else None,
            }
            logger.info(json.dumps(log_payload, default=str))

            try:
                async with SessionLocal() as db:
                    db.add(
                        APIRequestLog(
                            trace_id=trace_id,
                            user_id=user_id,
                            path=request.url.path,
                            method=request.method,
                            status_code=status_code,
                            latency_ms=elapsed_ms,
                        )
                    )
                    await db.commit()
            except Exception:
                logger.exception("Failed to persist API request log. trace_id=%s", trace_id)
            trace_id_ctx_var.reset(token)
