"""Loki MCP tools for log querying."""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.clients.base import APIError
from lgtm_mcp.clients.loki import LokiClient
from lgtm_mcp.config import get_instance_manager, load_config


def get_loki_client(instance: str | None = None) -> LokiClient:
    """Get a Loki client for the specified instance."""
    config = load_config()
    manager = get_instance_manager(config)
    instance_name = manager.get_instance(instance)
    backend_config = config.get_loki(instance_name)
    return LokiClient(backend_config, config.settings, instance_name=instance_name)


def register_loki_tools(mcp: FastMCP) -> None:
    """Register all Loki tools with the MCP server."""

    @mcp.tool()
    async def loki_query(
        query: str,
        start: str,
        end: str,
        limit: int = 20,
        direction: str = "backward",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Query logs from Loki. Use loki_patterns first for initial investigation.

        Args:
            query: LogQL query (e.g., '{app="myapp"} |= "error"')
            start: Start time (Unix epoch seconds or RFC3339)
            end: End time (Unix epoch seconds or RFC3339)
            limit: Max entries to return (default: 20)
            direction: "backward" (newest first) or "forward"
            instance: LGTM instance name
        """
        async with get_loki_client(instance) as client:
            response = await client.query_range(query, start, end, limit, direction)
            entries = response.get_log_entries()[:limit]
            max_line_length = 500
            for entry in entries:
                line = entry.get("line", "")
                if len(line) > max_line_length:
                    entry["line"] = line[:max_line_length] + "..."
                    entry["truncated"] = True
            if not entries:
                return {
                    "status": "success",
                    "count": 0,
                    "entries": [],
                    "message": "No logs found. Try adjusting the query or time range.",
                }
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "entries": entries,
                "count": len(entries),
            }

    @mcp.tool()
    async def loki_patterns(
        query: str,
        start: str,
        end: str,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Detect log patterns. Use FIRST when investigating logs - groups similar lines.

        Args:
            query: LogQL stream selector (e.g., '{app="myapp"}')
            start: Start time (Unix epoch seconds or RFC3339)
            end: End time (Unix epoch seconds or RFC3339)
            instance: LGTM instance name
        """
        async with get_loki_client(instance) as client:
            try:
                data = await client.get_patterns(query, start, end)
            except APIError as e:
                if e.status_code == 404:
                    return {
                        "status": "error",
                        "error": "patterns_not_available",
                        "message": "Patterns endpoint not available. Use loki_query instead.",
                    }
                raise
            patterns = data.get("data", [])
            if not patterns:
                return {
                    "status": "success",
                    "pattern_count": 0,
                    "patterns": [],
                    "message": "No patterns found. Use loki_query to check if logs exist.",
                }
            return {
                "status": "success",
                "pattern_count": len(patterns),
                "patterns": [
                    {
                        "pattern": p.get("pattern", ""),
                        "total_samples": sum(s[1] for s in p.get("samples", [])),
                    }
                    for p in patterns
                ],
            }

    @mcp.tool()
    async def loki_stats(
        query: str,
        start: str,
        end: str,
        include_volume: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get log statistics and optionally volume breakdown by labels.

        Args:
            query: LogQL matchers (e.g., '{app="myapp"}')
            start: Start time (Unix epoch seconds or RFC3339)
            end: End time (Unix epoch seconds or RFC3339)
            include_volume: Include volume breakdown by labels
            instance: LGTM instance name
        """
        async with get_loki_client(instance) as client:
            result: dict[str, Any] = {"status": "success"}

            try:
                stats = await client.get_index_stats(query, start, end)
                result["stats"] = stats
            except APIError as e:
                if e.status_code == 404:
                    result["stats"] = {"error": "stats endpoint not available"}
                else:
                    raise

            if include_volume:
                try:
                    volume = await client.get_volume(query, start, end)
                    result["volume"] = volume
                except APIError as e:
                    if e.status_code == 404:
                        result["volume"] = {"error": "volume endpoint not available"}
                    else:
                        raise

            return result

    @mcp.tool()
    async def loki_metric_query(
        query: str,
        time: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute metric-type LogQL (count_over_time, rate, etc.) at a point in time.

        Args:
            query: LogQL metric query (e.g., 'count_over_time({app="myapp"}[5m])')
            time: Evaluation timestamp (default: now)
            instance: LGTM instance name
        """
        async with get_loki_client(instance) as client:
            response = await client.instant_query(query, time, 100)
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "result": [r.model_dump() for r in response.data.result],
            }

    @mcp.tool()
    async def loki_metadata(
        info: Literal["labels", "label_values", "series"],
        label: str | None = None,
        query: str | None = None,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get Loki metadata: labels, label values, or series.

        Args:
            info: What to get - "labels", "label_values", or "series"
            label: Label name (required for label_values)
            query: LogQL selector to scope results (required for series, optional for others)
            start: Start time filter
            end: End time filter
            instance: LGTM instance name
        """
        async with get_loki_client(instance) as client:
            if info == "labels":
                labels = await client.get_labels(start, end, query)
                if not labels:
                    return {"status": "success", "labels": [], "message": "No labels found."}
                return {"status": "success", "labels": labels, "count": len(labels)}

            elif info == "label_values":
                if not label:
                    return {
                        "status": "error",
                        "message": "label parameter required for label_values",
                    }
                values = await client.get_label_values(label, start, end, query)
                if not values:
                    return {
                        "status": "success",
                        "label": label,
                        "values": [],
                        "message": f"No values for label '{label}'.",
                    }
                return {"status": "success", "label": label, "values": values, "count": len(values)}

            elif info == "series":
                if not query:
                    return {"status": "error", "message": "query parameter required for series"}
                series = await client.get_series([query], start, end)
                if not series:
                    return {"status": "success", "series": [], "message": "No series found."}
                return {"status": "success", "series": series, "count": len(series)}

            else:
                return {"status": "error", "message": f"Unknown info type: {info}"}
