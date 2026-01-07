"""
True async OpenTelemetry observability implementation for the Dashboard API.
Provides comprehensive tracing, metrics, and logging integration with proper async support.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings

logger = logging.getLogger(__name__)


class Observability:
    """Async OpenTelemetry observability configuration."""

    _initialized = False
    _tracer_provider = None
    _meter_provider = None
    _lock = asyncio.Lock()

    @classmethod
    async def initialize(cls, service_name: str = "", service_version: str = ""):
        """Async initialize OpenTelemetry tracing and metrics with thread safety."""
        async with cls._lock:
            if cls._initialized:
                logger.info("Observability already initialized")
                return

            try:
                # Run initialization in thread pool to avoid blocking async loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, cls._sync_initialize, service_name, service_version
                )
                cls._initialized = True
                logger.info("OpenTelemetry observability initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize observability: {str(e)}")
                # Set initialized to True to prevent repeated failed attempts
                cls._initialized = True

    @classmethod
    def _sync_initialize(cls, service_name: str, service_version: str):
        """Synchronous initialization called from thread pool."""
        service_name = service_name or settings.APP_NAME
        service_version = service_version or settings.VERSION

        # Create resource
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            }
        )

        # Setup tracing
        cls._setup_tracing(resource)

        # Setup metrics
        cls._setup_metrics(resource)

    @classmethod
    def _setup_tracing(cls, resource: Resource):
        """Setup OpenTelemetry tracing."""
        tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter if environment variables are set
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            otlp_exporter = OTLPSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        trace.set_tracer_provider(tracer_provider)
        cls._tracer_provider = tracer_provider

    @classmethod
    def _setup_metrics(cls, resource: Resource):
        """Setup OpenTelemetry metrics."""
        # Add OTLP exporter if environment variables are set
        metric_reader = None
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            metric_exporter = OTLPMetricExporter()
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=5000,  # 5 seconds
            )

        meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader] if metric_reader else []
        )
        metrics.set_meter_provider(meter_provider)
        cls._meter_provider = meter_provider

    @classmethod
    async def get_tracer(cls, name: str = ""):
        """Get a tracer instance async with initialization guarantee."""
        if not cls._initialized:
            await cls.initialize()
        return trace.get_tracer(name or settings.APP_NAME)

    @classmethod
    async def get_meter(cls, name: str = ""):
        """Get a meter instance async with initialization guarantee."""
        if not cls._initialized:
            await cls.initialize()
        return metrics.get_meter(name or settings.APP_NAME)

    @classmethod
    async def record_opentelemetry_metrics(
        cls,
        metric_name: str,
        value: float = 1.0,
        metric_type: str = "counter",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Async record metrics using OpenTelemetry."""
        if not cls._initialized:
            return

        meter = await cls.get_meter()
        if metric_type == "counter":
            counter = meter.create_counter(name=metric_name)
            counter.add(value, attributes or {})
        elif metric_type == "histogram":
            histogram = meter.create_histogram(name=metric_name)
            histogram.record(value, attributes or {})


# Prometheus metrics - thread-safe and can be used in async context
DASHBOARD_REQUESTS = Counter(
    "dashboard_requests_total",
    "Total dashboard requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

CACHE_HITS = Counter("cache_hits_total", "Total cache hits", ["cache_type"])
CACHE_MISSES = Counter("cache_misses_total", "Total cache misses", ["cache_type"])

DB_CONNECTIONS = Gauge("database_connections_active", "Active database connections")
REQUEST_IN_PROGRESS = Gauge("requests_in_progress", "Requests in progress")

# Business metrics
DASHBOARDS_CREATED = Counter("dashboards_created_total", "Total dashboards created")


async def setup_observability(app):
    """Async setup comprehensive observability for FastAPI application."""
    try:
        # Initialize OpenTelemetry async
        await Observability.initialize()

        # Setup Prometheus instrumentation
        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=True,
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics", "/health"],
            env_var_name="ENABLE_METRICS",
            inprogress_name="inprogress",
            inprogress_labels=True,
        )

        instrumentator.instrument(app).expose(app, endpoint="/metrics")
        logger.info("Observability setup completed successfully")
        return instrumentator

    except Exception as e:
        logger.error(f"Failed to setup observability: {str(e)}")
        raise


@asynccontextmanager
async def trace_operation(
    operation_name: str, attributes: Optional[Dict[str, Any]] = None
):
    """Async context manager for tracing operations with proper error handling."""
    if attributes is None:
        attributes = {}

    tracer = await Observability.get_tracer()
    with tracer.start_as_current_span(operation_name, attributes=attributes) as span:
        start_time = time.time()
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute("duration", duration)


async def record_request_metrics(
    method: str, endpoint: str, status_code: int, duration: float
):
    """Async record request metrics for Prometheus with OpenTelemetry integration."""
    try:
        # Prometheus metrics (thread-safe)
        DASHBOARD_REQUESTS.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).inc()
        REQUEST_DURATION.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).observe(duration)

        # OpenTelemetry metrics (async-safe)
        if Observability._initialized:
            meter = await Observability.get_meter()
            request_duration_histogram = meter.create_histogram(
                name="http.request.duration",
                description="HTTP request duration in seconds",
                unit="s",
            )
            request_duration_histogram.record(
                duration,
                attributes={
                    "http.method": method,
                    "http.route": endpoint,
                    "http.status_code": status_code,
                },
            )

    except Exception as e:
        logger.error(f"Error recording request metrics: {str(e)}")


async def record_cache_metrics(cache_type: str, hit: bool):
    """Async record cache metrics with OpenTelemetry integration."""
    try:
        # Prometheus metrics
        if hit:
            CACHE_HITS.labels(cache_type=cache_type).inc()
        else:
            CACHE_MISSES.labels(cache_type=cache_type).inc()

        # OpenTelemetry metrics
        if Observability._initialized:
            meter = await Observability.get_meter()
            cache_counter = meter.create_counter(
                name="cache.operations",
                description="Cache operations total",
            )
            cache_counter.add(
                1,
                attributes={
                    "cache.type": cache_type,
                    "cache.result": "hit" if hit else "miss",
                },
            )

    except Exception as e:
        logger.error(f"Error recording cache metrics: {str(e)}")


async def record_business_metrics(
    metric_name: str, value: int = 1, labels: Optional[Dict[str, str]] = None
):
    """Async record business metrics with OpenTelemetry integration."""
    try:
        # Prometheus metrics for specific business events
        if metric_name == "dashboards_created":
            DASHBOARDS_CREATED.inc(value)

        # OpenTelemetry metrics
        if Observability._initialized:
            meter = await Observability.get_meter()
            business_counter = meter.create_counter(
                name=f"business.{metric_name}",
                description=f"Business metric: {metric_name}",
            )
            attributes = labels or {}
            business_counter.add(value, attributes=attributes)

    except Exception as e:
        logger.error(f"Error recording business metrics: {str(e)}")


async def get_system_metrics() -> Dict[str, Any]:
    """Async get comprehensive system metrics with error handling."""
    try:
        # Run system metrics collection in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_get_system_metrics)
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        return {"error": str(e), "timestamp": time.time(), "success": False}


def _sync_get_system_metrics() -> Dict[str, Any]:
    """Synchronous system metrics collection."""
    import psutil

    metrics = {}

    try:
        # CPU Metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics["cpu"] = {
            "system_percent": cpu_percent,
            "core_count": psutil.cpu_count(),
            "per_cpu_percent": psutil.cpu_percent(percpu=True),
        }

        # Memory Metrics
        memory_info = psutil.virtual_memory()
        metrics["memory"] = {
            "total_bytes": memory_info.total,
            "available_bytes": memory_info.available,
            "used_bytes": memory_info.used,
            "percent": memory_info.percent,
            "free_bytes": memory_info.free,
        }

        # Disk Metrics
        disk_info = psutil.disk_usage("/")
        metrics["disk"] = {
            "total_bytes": disk_info.total,
            "used_bytes": disk_info.used,
            "free_bytes": disk_info.free,
            "percent": disk_info.percent,
        }

        # Network Metrics
        net_io = psutil.net_io_counters()
        metrics["network"] = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }

        # Process Metrics
        process = psutil.Process(os.getpid())
        with process.oneshot():
            metrics["process"] = {
                "cpu_percent": process.cpu_percent(),
                "memory_rss_bytes": process.memory_info().rss,
                "memory_percent": process.memory_percent(),
                "threads": process.num_threads(),
                "create_time": process.create_time(),
            }

        metrics["timestamp"] = time.time()
        metrics["success"] = True

    except Exception as e:
        metrics["error"] = str(e)
        metrics["timestamp"] = time.time()
        metrics["success"] = False

    return metrics
