"""MCP resources for Prometheus metric metadata discovery."""

import json

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.clients.prometheus import PrometheusClient
from lgtm_mcp.config import load_config


def register_metric_resources(mcp: FastMCP) -> None:
    """Register metric metadata resources with the MCP server."""

    @mcp.resource("lgtm://{instance}/prometheus/metrics")
    async def prometheus_metrics(instance: str) -> str:
        """Get all Prometheus metric names for an instance.

        Returns JSON with metric names available for querying.
        """
        config = load_config()
        backend_config = config.get_prometheus(instance)
        async with PrometheusClient(backend_config, config.settings) as client:
            metrics = await client.get_metric_names()
            return json.dumps(
                {
                    "metrics": metrics[:5000],
                    "count": len(metrics),
                    "truncated": len(metrics) > 5000,
                }
            )

    @mcp.resource("lgtm://{instance}/prometheus/metrics/{name}")
    async def prometheus_metric_metadata(instance: str, name: str) -> str:
        """Get metadata for a specific Prometheus metric.

        Returns JSON with metric type, help text, and unit.
        """
        config = load_config()
        backend_config = config.get_prometheus(instance)
        async with PrometheusClient(backend_config, config.settings) as client:
            metadata = await client.get_metadata(name)
            if name in metadata:
                return json.dumps(
                    {
                        "metric": name,
                        "metadata": metadata[name],
                    }
                )
            return json.dumps(
                {
                    "metric": name,
                    "metadata": [],
                    "error": f"No metadata found for metric: {name}",
                }
            )
