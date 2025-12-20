"""Prometheus MCP tools for metrics querying."""

from typing import Any

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
    async def prometheus_instant_query(
        query: str,
        time: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute PromQL instant query at a single point in time.

        Args:
            query: PromQL query string (e.g., 'up{job="prometheus"}')
            time: Evaluation timestamp (default: now)
            instance: LGTM instance name

        Returns:
            Dictionary with instant query result
        """
        async with get_prometheus_client(instance) as client:
            response = await client.instant_query(query, time)
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "result": response.get_instant_values(),
                "warnings": response.warnings,
            }

    @mcp.tool()
    async def prometheus_range_query(
        query: str,
        start: str,
        end: str,
        step: str = "1m",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute PromQL range query over a time period.

        Args:
            query: PromQL query string
            start: Start timestamp (Unix epoch or RFC3339)
            end: End timestamp (Unix epoch or RFC3339)
            step: Query resolution step (e.g., "15s", "1m", "5m")
            instance: LGTM instance name

        Returns:
            Dictionary with range query result containing time series
        """
        async with get_prometheus_client(instance) as client:
            response = await client.range_query(query, start, end, step)
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "result": response.get_range_values(),
                "warnings": response.warnings,
            }

    @mcp.tool()
    async def prometheus_get_metric_names(
        match: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """List available metric names in Prometheus.

        Args:
            match: Optional series selector to filter metrics
            instance: LGTM instance name

        Returns:
            List of metric names
        """
        async with get_prometheus_client(instance) as client:
            return await client.get_metric_names(match)

    @mcp.tool()
    async def prometheus_get_label_names(
        match: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """List label names in Prometheus.

        Args:
            match: Series selector(s) to filter labels
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of label names
        """
        async with get_prometheus_client(instance) as client:
            return await client.get_label_names(match, start, end)

    @mcp.tool()
    async def prometheus_get_label_values(
        label: str,
        match: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """Get values for a specific label in Prometheus.

        Args:
            label: Label name
            match: Series selector(s) to filter values
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of label values
        """
        async with get_prometheus_client(instance) as client:
            return await client.get_label_values(label, match, start, end)

    @mcp.tool()
    async def prometheus_get_series(
        match: list[str],
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[dict[str, str]]:
        """Find series matching label selectors.

        Args:
            match: Series selector(s) (e.g., ['up{job="prometheus"}'])
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of label sets for matching series
        """
        async with get_prometheus_client(instance) as client:
            return await client.get_series(match, start, end)

    @mcp.tool()
    async def prometheus_get_metadata(
        metric: str | None = None,
        instance: str | None = None,
    ) -> dict[str, list[dict]]:
        """Get metric metadata (type, help, unit).

        Args:
            metric: Optional metric name to filter
            instance: LGTM instance name

        Returns:
            Dictionary mapping metric names to metadata
        """
        async with get_prometheus_client(instance) as client:
            return await client.get_metadata(metric)

    @mcp.tool()
    async def prometheus_range_query_chart(
        query: str,
        start: str,
        end: str,
        step: str = "1m",
        height: int = 15,
        max_series: int = 5,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute PromQL range query and return ASCII chart visualization.

        Best for visualizing time-series trends. For raw data, use prometheus_range_query.

        Args:
            query: PromQL query string (e.g., 'rate(http_requests_total[5m])')
            start: Start timestamp (Unix epoch or RFC3339)
            end: End timestamp (Unix epoch or RFC3339)
            step: Query resolution step (e.g., "15s", "1m", "5m")
            height: Chart height in lines (default: 15)
            max_series: Maximum series to plot (default: 5)
            instance: LGTM instance name

        Returns:
            Dictionary with ASCII chart, legend, and metadata
        """
        async with get_prometheus_client(instance) as client:
            response = await client.range_query(query, start, end, step)
            series_data = response.get_range_values()
            result = plot_time_series(series_data, height=height, max_series=max_series)
            result["query"] = query
            return result
