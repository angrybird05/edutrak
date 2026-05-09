"""
Observability middleware — Request tracing, latency logging, and API request persistence.
"""
import json
import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.core.request_context import trace_id_ctx_var
from app.shared.db.session import SessionLocal
from app.modules.platform.models import APIRequestLog

logger = logging.getLogger(__name__)


def install_observability_middleware(app: FastAPI, slow_ms_threshold: int = 800) -> None:
    """Install HTTP middleware that traces every request."""

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

            user_id = getattr(request.state, "current_user_id", None)
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
