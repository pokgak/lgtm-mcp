"""Loki MCP tools for log querying."""

from typing import Any

from mcp.server.fastmcp import FastMCP

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
    async def loki_query_logs(
        query: str,
        start: str,
        end: str,
        limit: int = 100,
        direction: str = "backward",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute LogQL query over a time range to retrieve logs.

        Args:
            query: LogQL query string (e.g., '{app="myapp"} |= "error"')
            start: Start timestamp (Unix epoch seconds or RFC3339)
            end: End timestamp (Unix epoch seconds or RFC3339)
            limit: Maximum log entries to return (default: 100)
            direction: Query direction - "backward" (newest first) or "forward"
            instance: LGTM instance name (uses default if not specified)

        Returns:
            Dictionary with log entries containing timestamp, labels, and line
        """
        async with get_loki_client(instance) as client:
            response = await client.query_range(query, start, end, limit, direction)
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "entries": response.get_log_entries()[:limit],
                "count": len(response.get_log_entries()),
            }

    @mcp.tool()
    async def loki_instant_query(
        query: str,
        time: str | None = None,
        limit: int = 100,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Execute metric-type LogQL query at a single point in time.

        Use this for aggregation queries like count_over_time, rate, etc.

        Args:
            query: LogQL metric query (e.g., 'count_over_time({app="myapp"}[5m])')
            time: Evaluation timestamp (default: now)
            limit: Maximum results to return
            instance: LGTM instance name

        Returns:
            Dictionary with query result
        """
        async with get_loki_client(instance) as client:
            response = await client.instant_query(query, time, limit)
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "result": [r.model_dump() for r in response.data.result],
            }

    @mcp.tool()
    async def loki_get_labels(
        start: str | None = None,
        end: str | None = None,
        query: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """List all known label names in Loki.

        Args:
            start: Start timestamp to filter labels
            end: End timestamp to filter labels
            query: LogQL query to scope labels (e.g., '{app="myapp"}')
            instance: LGTM instance name

        Returns:
            List of label names
        """
        async with get_loki_client(instance) as client:
            return await client.get_labels(start, end, query)

    @mcp.tool()
    async def loki_get_label_values(
        label: str,
        start: str | None = None,
        end: str | None = None,
        query: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """Get values for a specific label in Loki.

        Args:
            label: Label name to get values for
            start: Start timestamp to filter values
            end: End timestamp to filter values
            query: LogQL query to scope values
            instance: LGTM instance name

        Returns:
            List of label values
        """
        async with get_loki_client(instance) as client:
            return await client.get_label_values(label, start, end, query)

    @mcp.tool()
    async def loki_get_series(
        match: list[str],
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[dict[str, str]]:
        """Find log streams matching label selectors.

        Args:
            match: List of label selector strings (e.g., ['{app="myapp"}'])
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of label sets for matching streams
        """
        async with get_loki_client(instance) as client:
            return await client.get_series(match, start, end)
