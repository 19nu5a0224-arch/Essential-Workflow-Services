"""
Main application entry point for the dashboard API with OpenTelemetry observability.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.database import db_manager
from app.core.logging import (
    RequestContextManager,
    get_request_id,
)
from app.monitoring import (
    Observability,
    get_system_metrics,
    record_request_metrics,
    trace_operation,
)
from app.routers.comment_routers import router as comments_router
from app.routers.dashboard_routers import router as dashboard_router
from app.routers.feature_routers import router as feature_router
from app.routers.internal_router import router as internal_router
from app.routers.n8n_workflows_router import router as n8n_workflows_router
from app.routers.widget_locking_router import router as widget_locking_router
from app.utils.cache import initialize_cache

logger = logging.getLogger(__name__)

# Global instrumentator variable
instrumentator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    try:
        logger.info(f"Starting {settings.APP_NAME}...")

        await db_manager.initialize(
            database_url=settings.DATABASE_URL,
            debug=settings.DEBUG,
        )

        await db_manager.create_tables()

        logger.info("Database initialized successfully")

        # Warm up connection pool
        await db_manager.warmup_connections(min_connections=10)
        logger.info("Connection pool warmup completed")

        # Initialize cache
        await initialize_cache()
        logger.info("Cache initialized successfully")

        # Initialize widget locking service
        from app.services.widget_locking_service import (
            initialize_widget_locking_service,
        )

        await initialize_widget_locking_service()
        logger.info("Widget locking service initialized successfully")

        # Start background cleanup service
        from app.services.session_cleanup_service import start_background_cleanup

        await start_background_cleanup()
        logger.info("Background cleanup service started successfully")

        # Initialize observability after database setup
        await Observability.initialize()

        yield

    finally:
        logger.info("Shutting down application...")
        await db_manager.close()
        logger.info("Database connections closed")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)
logger = logging.getLogger(__name__)

# Track startup time for uptime calculation
startup_time = time.time()

# Observability is initialized in the lifespan manager


# Combined middleware for observability and request ID
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Async middleware for OpenTelemetry observability and request ID tracing."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.time()

    async with RequestContextManager(request_id):
        async with trace_operation(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.request_id": request_id,
            },
        ):
            logger.info(f"Request started: {request.method} {request.url.path}")

            # Process request
            response = await call_next(request)

            # Record metrics async
            duration = time.time() - start_time
            await record_request_metrics(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration=duration,
            )

            # Set response headers
            response.headers["X-Request-ID"] = get_request_id() or request_id
            response.headers["Server-Timing"] = f"total;dur={duration * 1000:.2f}"

            logger.info(
                f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.3f}s"
            )
            return response


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Observability setup is handled in lifespan manager


@app.get("/")
async def root(request: Request, current_user: dict = Depends(get_current_user)):
    """Root endpoint with request ID."""
    return {
        "message": f"{settings.APP_NAME} is running",
        "user_id": current_user["user_id"],
        "request_id": get_request_id(),
        "version": settings.VERSION,
    }


@app.get("/health")
async def health(request: Request):
    """Comprehensive health check endpoint with system metrics."""
    start_time = time.time()

    # Database health check
    is_db_healthy = await db_manager.health_check()
    status = "healthy" if is_db_healthy else "unhealthy"
    reason = None if is_db_healthy else "database connection failure"

    # Get comprehensive system metrics
    system_metrics = await get_system_metrics()

    # Calculate duration
    duration_ms = round((time.time() - start_time) * 1000, 2)

    # Convert timestamp to ISO format
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).isoformat()

    # Process system metrics to match the exact structure
    system_info = {}
    if "cpu" in system_metrics:
        system_info["cpu"] = {
            "system_percent": round(system_metrics["cpu"]["system_percent"], 1),
            "core_count": system_metrics["cpu"]["core_count"],
        }

    if "memory" in system_metrics:
        system_info["memory"] = {
            "total_bytes": system_metrics["memory"]["total_bytes"],
            "available_bytes": system_metrics["memory"]["available_bytes"],
            "used_bytes": system_metrics["memory"]["used_bytes"],
            "percent": round(system_metrics["memory"]["percent"], 1),
        }

    if "disk" in system_metrics:
        system_info["disk"] = {
            "total_bytes": system_metrics["disk"]["total_bytes"],
            "used_bytes": system_metrics["disk"]["used_bytes"],
            "free_bytes": system_metrics["disk"]["free_bytes"],
            "percent": round(system_metrics["disk"]["percent"], 1),
        }

    if "process" in system_metrics:
        system_info["process"] = {
            "cpu_percent": round(system_metrics["process"]["cpu_percent"], 1),
            "memory_rss_bytes": system_metrics["process"]["memory_rss_bytes"],
            "memory_percent": round(system_metrics["process"]["memory_percent"], 4),
            "threads": system_metrics["process"]["threads"],
        }

    return {
        "status": status,
        "reason": reason,
        "request_id": str(get_request_id() or uuid.uuid4()),
        "timestamp": timestamp,
        "version": settings.VERSION,
        "duration_ms": duration_ms,
        "uptime_seconds": round(time.time() - startup_time, 2),
        "components": {
            "database": "connected" if is_db_healthy else "disconnected",
            "api": "available",
            "metrics": "enabled",
        },
        "system": system_info,
        "business_summary": {
            "dashboards_created": "tracked_via_metrics",
            "requests_processed": "tracked_via_metrics",
        },
        "observability": {
            "opentelemetry": "enabled",
            "prometheus": "enabled",
            "tracing": "enabled",
            "metrics": "enabled",
        },
    }


# Include dashboard router
app.include_router(dashboard_router)
app.include_router(feature_router)
app.include_router(internal_router)
app.include_router(comments_router)
app.include_router(n8n_workflows_router)
app.include_router(widget_locking_router)
