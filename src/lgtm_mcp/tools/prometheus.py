"""Prometheus MCP tools for metrics querying."""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.clients.prometheus import PrometheusClient
from lgtm_mcp.config import get_instance_manager, load_config
from lgtm_mcp.utils.charts import plot_time_series


def get_prometheus_client(instance: str | None = None) -> PrometheusClient:
    """Get a Prometheus client for the specified instance."""
    config = load_config()
    manager = get_instance_manager(config)
    instance_name = manager.get_instance(instance)
    backend_config = config.get_prometheus(instance_name)
    return PrometheusClient(backend_config, config.settings, instance_name=instance_name)


def register_prometheus_tools(mcp: FastMCP) -> None:
    """Register all Prometheus tools with the MCP server."""

    @mcp.tool()
    async def prometheus_query(
        query: str,
        start: str | None = None,
        end: str | None = None,
        step: str = "1m",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute PromQL query. Instant query if no start/end, range query otherwise.

        Args:
            query: PromQL query (e.g., 'up{job="prometheus"}')
            start: Start time for range query (Unix epoch or RFC3339)
            end: End time for range query (Unix epoch or RFC3339)
            step: Resolution step for range query (e.g., "15s", "1m")
            instance: LGTM instance name
        """
        async with get_prometheus_client(instance) as client:
            if start and end:
                response = await client.range_query(query, start, end, step)
                result = response.get_range_values()
            else:
                response = await client.instant_query(query, start)
                result = response.get_instant_values()

            if not result:
                return {
                    "status": "success",
                    "result_type": response.data.resultType,
                    "result": [],
                    "message": "No data found. Check metric name or time range.",
                }
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "result": result,
                "warnings": response.warnings,
            }

    @mcp.tool()
    async def prometheus_chart(
        query: str,
        start: str,
        end: str,
        step: str = "1m",
        height: int = 12,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute PromQL range query and return ASCII chart visualization.

        Args:
            query: PromQL query (e.g., 'rate(http_requests_total[5m])')
            start: Start time (Unix epoch or RFC3339)
            end: End time (Unix epoch or RFC3339)
            step: Resolution step (e.g., "15s", "1m", "5m")
            height: Chart height in lines (default: 12)
            instance: LGTM instance name
        """
        async with get_prometheus_client(instance) as client:
            response = await client.range_query(query, start, end, step)
            series_data = response.get_range_values()
            if not series_data:
                return {
                    "status": "success",
                    "charts": [],
                    "message": "No data to chart. Check metric name or time range.",
                }
            result = plot_time_series(series_data, height=height, max_series=5)
            result["query"] = query
            return result

    @mcp.tool()
    async def prometheus_metadata(
        info: Literal["metrics", "labels", "label_values", "series", "metric_metadata"],
        metric: str | None = None,
        label: str | None = None,
        match: str | None = None,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get Prometheus metadata: metrics, labels, label values, series, or metric metadata.

        Args:
            info: What to get - "metrics", "labels", "label_values", "series", "metric_metadata"
            metric: Metric name (for metric_metadata)
            label: Label name (required for label_values)
            match: Series selector to filter results
            start: Start time filter
            end: End time filter
            instance: LGTM instance name
        """
        async with get_prometheus_client(instance) as client:
            if info == "metrics":
                metrics = await client.get_metric_names(match)
                if not metrics:
                    return {"status": "success", "metrics": [], "message": "No metrics found."}
                return {"status": "success", "metrics": metrics, "count": len(metrics)}

            elif info == "labels":
                match_list = [match] if match else None
                labels = await client.get_label_names(match_list, start, end)
                if not labels:
                    return {"status": "success", "labels": [], "message": "No labels found."}
                return {"status": "success", "labels": labels, "count": len(labels)}

            elif info == "label_values":
                if not label:
                    return {"status": "error", "message": "label parameter required"}
                match_list = [match] if match else None
                values = await client.get_label_values(label, match_list, start, end)
                if not values:
                    return {
                        "status": "success",
                        "label": label,
                        "values": [],
                        "message": f"No values for label '{label}'.",
                    }
                return {"status": "success", "label": label, "values": values, "count": len(values)}

            elif info == "series":
                if not match:
                    return {"status": "error", "message": "match parameter required for series"}
                series = await client.get_series([match], start, end)
                if not series:
                    return {"status": "success", "series": [], "message": "No series found."}
                return {"status": "success", "series": series, "count": len(series)}

            elif info == "metric_metadata":
                metadata = await client.get_metadata(metric)
                if not metadata:
                    return {"status": "success", "metadata": {}, "message": "No metadata found."}
                return {"status": "success", "metadata": metadata}

            else:
                return {"status": "error", "message": f"Unknown info type: {info}"}
