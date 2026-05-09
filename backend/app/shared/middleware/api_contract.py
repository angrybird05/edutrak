"""
Standardized API contract handlers.

Installs global exception handlers that format all error responses into a
consistent envelope: { code, message, details, trace_id }
"""
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def install_api_contract_handlers(app: FastAPI) -> None:
    """Install exception handlers that normalize error responses."""

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
