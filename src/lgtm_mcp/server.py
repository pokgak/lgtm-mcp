"""LGTM MCP Server - Code mode: read-only access to Loki, Prometheus, and Tempo APIs.

Instead of many individual tools, exposes 2 code execution tools (search + execute)
where the agent writes Python code that runs server-side with LGTM clients in scope.
This keeps reference docs and raw API responses server-side, returning only what the
agent needs — analogous to Cloudflare MCP's "code mode" pattern.
"""

import asyncio
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.config import get_instance_manager, load_config
from lgtm_mcp.executor import execute_code, execute_search
from lgtm_mcp.tracing import init_tracing

mcp = FastMCP(
    "LGTM MCP Server",
)

# Build the type information strings (analogous to Cloudflare's CLOUDFLARE_TYPES / SPEC_TYPES)

REFERENCE_TYPES = """\
reference: dict with keys "logql", "promql", "traceql"
  Each value is a markdown string with full syntax documentation including:
  - Selectors, filters, operators, functions, aggregations
  - Examples for common query patterns

Example:
  # Find all PromQL aggregation operators
  lines = reference["promql"].split("\\n")
  return [l for l in lines if "sum" in l.lower() or "avg" in l.lower()]

  # Get TraceQL structural operator docs
  return reference["traceql"]
"""


def _build_execute_types() -> str:
    """Build type descriptions based on which backends are configured."""
    config = load_config()
    has_loki = any(inst.loki for inst in config.instances.values())
    has_prometheus = any(inst.prometheus for inst in config.instances.values())
    has_tempo = any(inst.tempo for inst in config.instances.values())

    parts = []

    if has_loki:
        parts.append("""\
loki (LokiClient):
  await loki.query_range(query, start, end, limit=100, direction="backward") -> LokiQueryResponse
    # .get_log_entries() -> list[dict] with keys: timestamp, line, labels
  await loki.instant_query(query, time=None, limit=100) -> LokiQueryResponse
    # For metric-type LogQL: count_over_time, rate, etc.
    # .data.result -> list of results with .model_dump()
  await loki.get_labels(start=None, end=None, query=None) -> list[str]
  await loki.get_label_values(label, start=None, end=None, query=None) -> list[str]
  await loki.get_series(match=['{app="x"}'], start=None, end=None) -> list[dict]
  await loki.get_patterns(query, start, end) -> dict  # Detect log patterns
  await loki.get_index_stats(query, start, end) -> dict  # streams, chunks, entries, bytes
  await loki.get_volume(query, start, end, limit=100) -> dict  # Volume by labels""")

    if has_prometheus:
        parts.append("""\
prometheus (PrometheusClient):
  await prometheus.instant_query(query, time=None) -> PrometheusQueryResponse
    # .get_instant_values() -> list[dict] with metric labels and value
  await prometheus.range_query(query, start, end, step="1m") -> PrometheusQueryResponse
    # .get_range_values() -> list[dict] with metric labels and values timeseries
  await prometheus.get_label_names(match=None, start=None, end=None) -> list[str]
  await prometheus.get_label_values(label, match=None, start=None, end=None) -> list[str]
  await prometheus.get_series(match=['{job="x"}'], start=None, end=None) -> list[dict]
  await prometheus.get_metric_names(match=None) -> list[str]
  await prometheus.get_metadata(metric=None) -> dict""")

    if has_tempo:
        parts.append("""\
tempo (TempoClient):
  await tempo.get_trace(trace_id, start=None, end=None) -> dict  # OTLP JSON
  await tempo.search(query=None, tags=None, min_duration=None, max_duration=None, limit=20, start=None, end=None) -> TempoSearchResponse
    # .traces -> list with traceID, rootServiceName, rootTraceName, durationMs, spanCount
  await tempo.get_tag_names(scope=None, start=None, end=None) -> list[str]
  await tempo.get_tag_values(tag, start=None, end=None) -> list[str]
  await tempo.get_services(start=None, end=None) -> list[str]""")

    parts.append("""\
Helper functions:
  summarize_trace(trace_data) -> dict  # Summary with stats, span tree from OTLP data""")

    return "\n\n".join(parts)


def _build_search_description() -> str:
    return (
        "Search LGTM query language references. Use to look up LogQL, PromQL, or TraceQL syntax.\n\n"
        "The code runs as an async Python function body with these available:\n\n"
        + REFERENCE_TYPES
        + "\nYour code must return a value. Write it as the body of an async function.\n\n"
        "Examples:\n\n"
        "# Look up how to filter by duration in TraceQL\n"
        'section = reference["traceql"]\n'
        'return [l for l in section.split("\\n") if "duration" in l.lower()]\n\n'
        "# Get LogQL parser expressions\n"
        'return reference["logql"]'
    )


def _build_execute_description(execute_types: str) -> str:
    return (
        "Execute Python code against LGTM backends (Loki logs, Prometheus metrics, Tempo traces).\n\n"
        "First use 'search' to look up query syntax, then write code using the available clients.\n\n"
        "Available in your code:\n\n"
        + execute_types
        + "\n\nYour code must be the body of an async function that returns the result.\n"
        "All client calls are async — use await.\n"
        'Times: Unix epoch seconds (str) or RFC3339. Durations: "100ms", "1s", "5m", "1h".\n\n'
        "Examples:\n\n"
        "# Discover available labels in Loki\n"
        "labels = await loki.get_labels()\n"
        "return labels\n\n"
        "# Query error logs\n"
        """resp = await loki.query_range('{app="myapp"} |= "error"', "1710200000", "1710300000", limit=20)\n"""
        "entries = resp.get_log_entries()[:20]\n"
        'return [{"line": e["line"][:200], "ts": e["timestamp"]} for e in entries]\n\n'
        "# Error rate with Prometheus\n"
        """resp = await prometheus.instant_query('sum(rate(http_requests_total{status=~"5.."}[5m]))')\n"""
        "return resp.get_instant_values()\n\n"
        "# Range query\n"
        """resp = await prometheus.range_query('rate(http_requests_total[5m])', "1710200000", "1710300000", step="1m")\n"""
        "return resp.get_range_values()\n\n"
        "# Search slow traces\n"
        """resp = await tempo.search(query='{resource.service.name="api"}', min_duration="1s", limit=10)\n"""
        'return [{"id": t.traceID, "service": t.rootServiceName, "duration_ms": t.durationMs} for t in resp.traces]\n\n'
        "# Get trace summary\n"
        'trace_data = await tempo.get_trace("abc123def456")\n'
        "return summarize_trace(trace_data)"
    )


def register_code_mode_tools(mcp: FastMCP) -> None:
    """Register code mode tools: search + execute."""

    execute_types = _build_execute_types()
    search_desc = _build_search_description()
    execute_desc = _build_execute_description(execute_types)

    @mcp.tool(description=search_desc)
    async def search(code: str) -> str:
        return await execute_search(code)

    @mcp.tool(description=execute_desc)
    async def execute(code: str, instance: str | None = None) -> str:
        return await execute_code(code, instance)


@mcp.tool()
def instances(
    action: Literal["list", "set_default"] = "list",
    name: str | None = None,
) -> dict[str, Any]:
    """Manage LGTM instances: list available instances or set default.

    Args:
        action: "list" to show instances, "set_default" to change default
        name: Instance name (required for set_default)
    """
    manager = get_instance_manager()

    if action == "list":
        return {"status": "success", "instances": manager.list_instances()}

    elif action == "set_default":
        if not name:
            return {"status": "error", "message": "name parameter required for set_default"}
        manager.set_default(name)
        return {"status": "success", "message": f"Default instance set to: {name}"}

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


register_code_mode_tools(mcp)


def main() -> None:
    """Main entry point for the MCP server."""
    init_tracing()
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
