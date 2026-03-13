"""Code execution engine for code mode tools.

Executes agent-written Python code with LGTM clients injected into scope.
Analogous to Cloudflare MCP's executor.ts pattern.
"""

import traceback
from typing import Any

from lgtm_mcp.clients.loki import LokiClient
from lgtm_mcp.clients.prometheus import PrometheusClient
from lgtm_mcp.clients.tempo import TempoClient
from lgtm_mcp.config import get_instance_manager, load_config
from lgtm_mcp.resources.syntax import LOGQL_SYNTAX, PROMQL_SYNTAX, TRACEQL_SYNTAX
from lgtm_mcp.tools.tempo import _compute_trace_summary, _extract_spans_from_otlp
from lgtm_mcp.truncate import truncate_response


def _get_references() -> dict[str, str]:
    """Get all query language references as a dict."""
    return {
        "logql": LOGQL_SYNTAX,
        "promql": PROMQL_SYNTAX,
        "traceql": TRACEQL_SYNTAX,
    }


def _get_client(backend: str, instance: str | None = None) -> Any:
    """Get a client for the specified backend and instance."""
    config = load_config()
    manager = get_instance_manager(config)
    instance_name = manager.get_instance(instance)

    if backend == "loki":
        backend_config = config.get_loki(instance_name)
        return LokiClient(backend_config, config.settings, instance_name=instance_name)
    elif backend == "prometheus":
        backend_config = config.get_prometheus(instance_name)
        return PrometheusClient(backend_config, config.settings, instance_name=instance_name)
    elif backend == "tempo":
        backend_config = config.get_tempo(instance_name)
        return TempoClient(backend_config, config.settings, instance_name=instance_name)
    else:
        raise ValueError(f"Unknown backend: {backend}")


async def execute_search(code: str) -> str:
    """Execute code against the reference docs (no network calls).

    The code has access to:
    - reference: dict with keys "logql", "promql", "traceql" containing syntax docs
    """
    references = _get_references()

    scope: dict[str, Any] = {
        "reference": references,
    }

    try:
        exec(
            "async def __execute():\n"
            + "\n".join(f"    {line}" for line in code.splitlines()),
            scope,
        )
        result = await scope["__execute"]()
        return truncate_response(result)
    except Exception as e:
        return f"Error: {e}\n{traceback.format_exc()}"


async def execute_code(code: str, instance: str | None = None) -> str:
    """Execute code against LGTM backends.

    The code has access to:
    - loki: LokiClient (if configured)
    - prometheus: PrometheusClient (if configured)
    - tempo: TempoClient (if configured)
    - summarize_trace(trace_data): Compute summary from OTLP trace data
    - plot_chart(series_data, height=12, max_series=5): ASCII chart from range query data
    """
    config = load_config()
    manager = get_instance_manager(config)
    instance_name = manager.get_instance(instance)
    instance_config = config.instances[instance_name]

    clients: list[Any] = []
    scope: dict[str, Any] = {}

    def _summarize_trace(trace_data: dict, max_tree_depth: int = 3, max_tree_spans: int = 20) -> dict:
        spans = _extract_spans_from_otlp(trace_data)
        if not spans:
            return {"error": "No spans found in trace data"}
        trace_id = spans[0]["trace_id"] if spans else "unknown"
        return _compute_trace_summary(trace_id, spans, max_tree_depth, max_tree_spans)

    scope["summarize_trace"] = _summarize_trace

    try:
        if instance_config.loki:
            loki = _get_client("loki", instance)
            clients.append(loki)
            scope["loki"] = loki

        if instance_config.prometheus:
            prometheus = _get_client("prometheus", instance)
            clients.append(prometheus)
            scope["prometheus"] = prometheus

        if instance_config.tempo:
            tempo = _get_client("tempo", instance)
            clients.append(tempo)
            scope["tempo"] = tempo

        exec(
            "async def __execute():\n"
            + "\n".join(f"    {line}" for line in code.splitlines()),
            scope,
        )
        result = await scope["__execute"]()
        return truncate_response(result)
    except Exception as e:
        return f"Error: {e}\n{traceback.format_exc()}"
    finally:
        for client in clients:
            await client.close()
