"""Tempo MCP tools for trace querying."""

import statistics
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.clients.base import APIError
from lgtm_mcp.clients.tempo import TempoClient
from lgtm_mcp.config import get_instance_manager, load_config


def _extract_spans_from_otlp(trace_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract flat list of spans from OTLP trace data."""
    spans = []
    batches = trace_data.get("batches", [])

    for batch in batches:
        resource = batch.get("resource", {})
        resource_attrs = {}
        for attr in resource.get("attributes", []):
            key = attr.get("key", "")
            value = attr.get("value", {})
            if "stringValue" in value:
                resource_attrs[key] = value["stringValue"]
            elif "intValue" in value:
                resource_attrs[key] = value["intValue"]

        service_name = resource_attrs.get("service.name", "unknown")

        scope_spans = batch.get("scopeSpans", [])
        for scope in scope_spans:
            for span in scope.get("spans", []):
                span_info = {
                    "trace_id": span.get("traceId", ""),
                    "span_id": span.get("spanId", ""),
                    "parent_span_id": span.get("parentSpanId", ""),
                    "name": span.get("name", ""),
                    "service": service_name,
                    "start_time_ns": int(span.get("startTimeUnixNano", 0)),
                    "end_time_ns": int(span.get("endTimeUnixNano", 0)),
                    "duration_ns": int(span.get("endTimeUnixNano", 0))
                    - int(span.get("startTimeUnixNano", 0)),
                    "status_code": span.get("status", {}).get("code", 0),
                    "kind": span.get("kind", 0),
                }
                spans.append(span_info)

    return spans


def _compute_trace_summary(
    trace_id: str, spans: list[dict[str, Any]], max_tree_depth: int, max_tree_spans: int
) -> dict[str, Any]:
    """Compute summary statistics from spans."""
    if not spans:
        return {"trace_id": trace_id, "error": "No spans found"}

    durations_ms = [s["duration_ns"] / 1_000_000 for s in spans]
    error_spans = [s for s in spans if s["status_code"] == 2]
    services = list(set(s["service"] for s in spans))

    span_counts_by_service: dict[str, int] = {}
    for s in spans:
        svc = s["service"]
        span_counts_by_service[svc] = span_counts_by_service.get(svc, 0) + 1

    root_span = None
    for s in spans:
        if not s["parent_span_id"]:
            root_span = s
            break
    if not root_span:
        root_span = min(spans, key=lambda s: s["start_time_ns"])

    trace_start = min(s["start_time_ns"] for s in spans)
    trace_end = max(s["end_time_ns"] for s in spans)
    total_duration_ms = (trace_end - trace_start) / 1_000_000

    sorted_durations = sorted(durations_ms)
    n = len(sorted_durations)

    def percentile(p: float) -> float:
        idx = int(p / 100 * (n - 1))
        return sorted_durations[idx]

    summary = {
        "trace_id": trace_id,
        "total_spans": len(spans),
        "total_duration_ms": round(total_duration_ms, 2),
        "services": services,
        "service_count": len(services),
        "root_span": {
            "name": root_span["name"],
            "service": root_span["service"],
            "duration_ms": round(root_span["duration_ns"] / 1_000_000, 2),
        },
        "error_count": len(error_spans),
        "error_spans": [
            {
                "name": s["name"],
                "service": s["service"],
                "duration_ms": round(s["duration_ns"] / 1_000_000, 2),
            }
            for s in error_spans[:5]
        ],
        "span_counts_by_service": span_counts_by_service,
        "duration_stats": {
            "min_ms": round(min(durations_ms), 2),
            "max_ms": round(max(durations_ms), 2),
            "avg_ms": round(statistics.mean(durations_ms), 2),
            "p50_ms": round(percentile(50), 2),
            "p95_ms": round(percentile(95), 2),
            "p99_ms": round(percentile(99), 2),
        },
        "span_tree": _build_span_tree(spans, root_span, max_tree_depth, max_tree_spans),
    }

    return summary


def _build_span_tree(
    spans: list[dict[str, Any]],
    root_span: dict[str, Any],
    max_depth: int,
    max_spans: int,
) -> list[str]:
    """Build a text representation of the span tree."""
    children_map: dict[str, list[dict[str, Any]]] = {}
    for s in spans:
        parent_id = s["parent_span_id"] or ""
        if parent_id not in children_map:
            children_map[parent_id] = []
        children_map[parent_id].append(s)

    for children in children_map.values():
        children.sort(key=lambda s: s["start_time_ns"])

    lines: list[str] = []
    span_count = [0]

    def format_span(span: dict[str, Any]) -> str:
        duration = round(span["duration_ns"] / 1_000_000, 2)
        error_marker = " [ERROR]" if span["status_code"] == 2 else ""
        return f"{span['service']}: {span['name']} ({duration}ms){error_marker}"

    def traverse(span: dict[str, Any], prefix: str, depth: int, is_last: bool) -> None:
        if span_count[0] >= max_spans:
            return
        span_count[0] += 1

        connector = "└─ " if is_last else "├─ "
        if depth == 0:
            lines.append(format_span(span))
        else:
            lines.append(f"{prefix}{connector}{format_span(span)}")

        if depth >= max_depth:
            children = children_map.get(span["span_id"], [])
            if children:
                child_prefix = prefix + ("   " if is_last else "│  ")
                lines.append(f"{child_prefix}└─ ... ({len(children)} more children)")
            return

        children = children_map.get(span["span_id"], [])
        child_prefix = prefix + ("   " if is_last else "│  ")
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            traverse(child, child_prefix, depth + 1, is_last_child)

    traverse(root_span, "", 0, True)

    if span_count[0] >= max_spans and len(spans) > span_count[0]:
        lines.append(f"... and {len(spans) - span_count[0]} more spans")

    return lines


def get_tempo_client(instance: str | None = None) -> TempoClient:
    """Get a Tempo client for the specified instance."""
    config = load_config()
    manager = get_instance_manager(config)
    instance_name = manager.get_instance(instance)
    backend_config = config.get_tempo(instance_name)
    return TempoClient(backend_config, config.settings, instance_name=instance_name)


def register_tempo_tools(mcp: FastMCP) -> None:
    """Register all Tempo tools with the MCP server."""

    @mcp.tool()
    async def tempo_get_trace(
        trace_id: str,
        start: str | None = None,
        end: str | None = None,
        summary: bool = True,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get trace by ID. Returns summary by default, full OTLP data if summary=False.

        Args:
            trace_id: Trace ID (hex string)
            start: Start time to narrow search
            end: End time to narrow search
            summary: Return summary with stats and span tree (default: True)
            instance: LGTM instance name
        """
        async with get_tempo_client(instance) as client:
            try:
                trace_data = await client.get_trace(trace_id, start, end)
            except APIError as e:
                if e.status_code == 404:
                    return {
                        "status": "error",
                        "error": "trace_not_found",
                        "trace_id": trace_id,
                        "message": "Trace not found. May have expired or ID incorrect.",
                    }
                raise

            if not summary:
                return trace_data

            spans = _extract_spans_from_otlp(trace_data)
            if not spans:
                return {
                    "status": "success",
                    "trace_id": trace_id,
                    "total_spans": 0,
                    "message": "Trace found but contains no spans.",
                }
            return _compute_trace_summary(trace_id, spans, max_tree_depth=3, max_tree_spans=20)

    @mcp.tool()
    async def tempo_search(
        query: str | None = None,
        min_duration: str | None = None,
        max_duration: str | None = None,
        limit: int = 20,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Search traces with TraceQL.

        Args:
            query: TraceQL query (e.g., '{resource.service.name="myapp"}')
            min_duration: Min duration (e.g., "100ms", "1s")
            max_duration: Max duration
            limit: Max traces to return (default: 20)
            start: Start time
            end: End time
            instance: LGTM instance name
        """
        async with get_tempo_client(instance) as client:
            try:
                response = await client.search(
                    query, None, min_duration, max_duration, limit, start, end
                )
            except APIError as e:
                if e.status_code == 404:
                    return {
                        "status": "error",
                        "error": "search_not_available",
                        "message": "Search endpoint not available on this Tempo instance.",
                    }
                raise
            if not response.traces:
                return {
                    "status": "success",
                    "traces": [],
                    "count": 0,
                    "message": "No traces found. Try expanding time range or relaxing filters.",
                }
            return {
                "status": "success",
                "traces": [t.model_dump() for t in response.traces],
                "count": len(response.traces),
            }

    @mcp.tool()
    async def tempo_metadata(
        info: Literal["services", "tags", "tag_values"],
        tag: str | None = None,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get Tempo metadata: services, tags, or tag values.

        Args:
            info: What to get - "services", "tags", or "tag_values"
            tag: Tag name (required for tag_values)
            start: Start time filter
            end: End time filter
            instance: LGTM instance name
        """
        async with get_tempo_client(instance) as client:
            try:
                if info == "services":
                    services = await client.get_services(start, end)
                    if not services:
                        return {
                            "status": "success",
                            "services": [],
                            "message": "No services found.",
                        }
                    return {"status": "success", "services": services, "count": len(services)}

                elif info == "tags":
                    tags = await client.get_tag_names(None, start, end)
                    if not tags:
                        return {"status": "success", "tags": [], "message": "No tags found."}
                    return {"status": "success", "tags": tags, "count": len(tags)}

                elif info == "tag_values":
                    if not tag:
                        return {
                            "status": "error",
                            "message": "tag parameter required for tag_values",
                        }
                    values = await client.get_tag_values(tag, start, end)
                    if not values:
                        return {
                            "status": "success",
                            "tag": tag,
                            "values": [],
                            "message": f"No values for tag '{tag}'.",
                        }
                    return {"status": "success", "tag": tag, "values": values, "count": len(values)}

                else:
                    return {"status": "error", "message": f"Unknown info type: {info}"}

            except APIError as e:
                if e.status_code == 404:
                    return {
                        "status": "error",
                        "error": f"{info}_not_available",
                        "message": f"The {info} endpoint is not available on this Tempo instance.",
                    }
                raise
