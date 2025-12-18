"""OpenTelemetry tracing setup for LGTM MCP server."""

import functools
import inspect
import os
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAME = "lgtm-mcp"
OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

QUERY_PARAM_NAMES = ("query", "q", "match", "trace_id")
QUERY_MAX_LENGTH = 100

T = TypeVar("T")

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


def traced_operation(
    operation: str | None = None,
    query_param: str | None = None,
) -> Callable:
    """
    Decorator for tracing client operations.

    Args:
        operation: Operation name (defaults to method name)
        query_param: Parameter name containing the query (auto-detected if None)

    Usage:
        @traced_operation()
        async def instant_query(self, query: str, time: str | None = None):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            op_name = operation or func.__name__
            backend_type = getattr(self, "backend_type", "unknown")
            instance_name = getattr(self, "instance_name", "unknown")
            span_name = f"{backend_type}.{op_name}"
            query_value = _extract_query(func, args, kwargs, query_param)

            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("lgtm.instance", instance_name)
                span.set_attribute("lgtm.backend", backend_type)
                span.set_attribute("lgtm.operation", op_name)
                if query_value:
                    span.set_attribute("lgtm.query", query_value[:QUERY_MAX_LENGTH])

                return await func(self, *args, **kwargs)

        return wrapper

    return decorator


def _extract_query(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    query_param: str | None,
) -> str | None:
    """Extract query value from function arguments."""
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Skip 'self' parameter - args don't include self since it's passed separately
    if params and params[0] == "self":
        params = params[1:]

    bound_args: dict[str, Any] = {}
    for i, arg in enumerate(args):
        if i < len(params):
            bound_args[params[i]] = arg
    bound_args.update(kwargs)

    if query_param and query_param in bound_args:
        return _format_query_value(bound_args[query_param])

    for param_name in QUERY_PARAM_NAMES:
        if param_name in bound_args:
            return _format_query_value(bound_args[param_name])

    return None


def _format_query_value(value: Any) -> str:
    """Format query value for tracing attribute."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)
