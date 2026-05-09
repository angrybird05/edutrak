import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from strawberry.fastapi import GraphQLRouter

from app.core.config import settings
from app.core.rate_limit import request_ip_limiter
from app.api_router import api_router
from app.shared.middleware.api_contract import install_api_contract_handlers
from app.shared.middleware.observability import install_observability_middleware
from app.shared.middleware.security_headers import SecurityHeadersMiddleware

# Import module event subscribers to guarantee they are registered at startup
import app.modules.analytics.events  # noqa
import app.modules.analytics.insights_v2.events  # noqa
import app.modules.platform.events  # noqa

from app.graphql.schema import schema
from app.graphql.context import get_context

# Configure logging
logging.basicConfig(
    level=settings.LOGGING_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: Connect DB, start Celery task queues, etc.
    """
    logger.info("Starting EduTrack modular monolith.")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Initialize background task queues
    from app.modules.analytics.task_queue import ai_insight_task_queue
    from app.modules.analytics.insights_v2.tasks import ai_insights_v2_task_queue
    await ai_insight_task_queue.start()
    await ai_insights_v2_task_queue.start()

    yield

    logger.info("Shutting down EduTrack Modular Monolith gracefully...")
    await ai_insight_task_queue.stop()
    await ai_insights_v2_task_queue.stop()
    from app.core.redis import redis_manager
    await redis_manager.close()


app = FastAPI(
    title=f"{settings.PROJECT_NAME} (Modular Monolith)",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)


# === Middleware ===

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Nginx limits this externally, but we keep it here as defense-in-depth
        max_size = 50 * 1024 * 1024  # 50 MB
        if "content-length" in request.headers:
            content_length = int(request.headers["content-length"])
            if content_length > max_size:
                from fastapi import HTTPException
                raise HTTPException(status_code=413, detail="Request body too large")
        return await call_next(request)

app.add_middleware(MaxBodySizeMiddleware)
install_observability_middleware(app, slow_ms_threshold=2000)
install_api_contract_handlers(app)
app.add_middleware(SecurityHeadersMiddleware)

# CORS is handled by Nginx in hosted environments, but local dev requires it here.
# In development, allow localhost/127.0.0.1 on any port so different frontend dev servers work.
if settings.ENVIRONMENT == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
elif settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# === Global Rate Limiter (Fallback if Nginx is bypassed) ===

@app.middleware("http")
async def apply_rate_limit(request: Request, call_next):
    # Exempt health checks, docs, and preflight requests from rate limiting
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path in [f"{settings.API_V1_STR}/health", "/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    # Local development often runs frontend and backend on different localhost ports.
    # Bypass the fallback limiter for those browser requests and let app-level auth handle them.
    if settings.ENVIRONMENT == "development":
        origin = (request.headers.get("origin") or "").rstrip("/")
        client_ip = request.client.host if request.client else "unknown"
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:") or client_ip in ["127.0.0.1", "::1", "localhost"]:
            return await call_next(request)
        
    client_ip = request.client.host if request.client else "unknown"
    if not await request_ip_limiter.allow(client_ip):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    return await call_next(request)


# === Routing ===

# Mount the domain module REST router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount the Strawberry GraphQL endpoint
graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix="/graphql")


# === Health Check Fallback ===
@app.get("/health", tags=["system"])
async def root_health():
    return {"status": "ok", "version": "1.0.0"}
