"""MCP resources for label discovery."""

import json

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.clients.loki import LokiClient
from lgtm_mcp.clients.prometheus import PrometheusClient
from lgtm_mcp.clients.tempo import TempoClient
from lgtm_mcp.config import load_config


def register_label_resources(mcp: FastMCP) -> None:
    """Register label discovery resources with the MCP server."""

    @mcp.resource("lgtm://{instance}/loki/labels")
    async def loki_labels(instance: str) -> str:
        """Get all Loki label names for an instance.

        Returns JSON with label names for use in LogQL queries.
        """
        config = load_config()
        backend_config = config.get_loki(instance)
        async with LokiClient(backend_config, config.settings) as client:
            labels = await client.get_labels()
            return json.dumps({"labels": labels, "count": len(labels)})

    @mcp.resource("lgtm://{instance}/loki/labels/{label}/values")
    async def loki_label_values(instance: str, label: str) -> str:
        """Get values for a specific Loki label.

        Returns JSON with label values.
        """
        config = load_config()
        backend_config = config.get_loki(instance)
        async with LokiClient(backend_config, config.settings) as client:
            values = await client.get_label_values(label)
            return json.dumps(
                {
                    "label": label,
                    "values": values[:1000],
                    "count": len(values),
                    "truncated": len(values) > 1000,
                }
            )

    @mcp.resource("lgtm://{instance}/prometheus/labels")
    async def prometheus_labels(instance: str) -> str:
        """Get all Prometheus label names for an instance.

        Returns JSON with label names for use in PromQL queries.
        """
        config = load_config()
        backend_config = config.get_prometheus(instance)
        async with PrometheusClient(backend_config, config.settings) as client:
            labels = await client.get_label_names()
            return json.dumps({"labels": labels, "count": len(labels)})

    @mcp.resource("lgtm://{instance}/prometheus/labels/{label}/values")
    async def prometheus_label_values(instance: str, label: str) -> str:
        """Get values for a specific Prometheus label.

        Returns JSON with label values (paginated for high-cardinality labels).
        """
        config = load_config()
        backend_config = config.get_prometheus(instance)
        async with PrometheusClient(backend_config, config.settings) as client:
            values = await client.get_label_values(label)
            return json.dumps(
                {
                    "label": label,
                    "values": values[:1000],
                    "count": len(values),
                    "truncated": len(values) > 1000,
                }
            )

    @mcp.resource("lgtm://{instance}/tempo/tags")
    async def tempo_tags(instance: str) -> str:
        """Get all Tempo tag names for an instance.

        Returns JSON with tag names for use in TraceQL queries.
        """
        config = load_config()
        backend_config = config.get_tempo(instance)
        async with TempoClient(backend_config, config.settings) as client:
            tags = await client.get_tag_names()
            return json.dumps({"tags": tags, "count": len(tags)})

    @mcp.resource("lgtm://{instance}/tempo/tags/{tag}/values")
    async def tempo_tag_values(instance: str, tag: str) -> str:
        """Get values for a specific Tempo tag.

        Returns JSON with tag values.
        """
        config = load_config()
        backend_config = config.get_tempo(instance)
        async with TempoClient(backend_config, config.settings) as client:
            values = await client.get_tag_values(tag)
            return json.dumps(
                {
                    "tag": tag,
                    "values": values[:1000],
                    "count": len(values),
                    "truncated": len(values) > 1000,
                }
            )
