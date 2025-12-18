"""OpenTelemetry tracing setup for LGTM MCP server."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAME = "lgtm-mcp"
OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

_initialized = False


def init_tracing() -> None:
    """Initialize OpenTelemetry tracing with OTLP gRPC exporter."""
    global _initialized
    if _initialized:
        return

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": "0.1.0",
        }
    )

    provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(
        endpoint=OTEL_ENDPOINT,
        insecure=True,
    )

    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()

    _initialized = True


def get_tracer(name: str = SERVICE_NAME) -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)
