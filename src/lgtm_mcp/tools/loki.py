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
    async def loki_patterns(
        query: str,
        start: str,
        end: str,
        step: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Detect log patterns and their frequency. Use this FIRST when investigating logs.

        Automatically groups similar log lines into patterns, showing which patterns
        are most common. Much more efficient than fetching raw logs for understanding
        log structure and identifying issues.

        Requires pattern_ingester to be enabled in Loki.

        Args:
            query: LogQL stream selector (e.g., '{app="myapp"}')
            start: Start timestamp (Unix epoch seconds or RFC3339)
            end: End timestamp (Unix epoch seconds or RFC3339)
            step: Step between samples for pattern frequency (optional)
            instance: LGTM instance name

        Returns:
            Dictionary with patterns and their sample counts over time
        """
        async with get_loki_client(instance) as client:
            data = await client.get_patterns(query, start, end, step)
            patterns = data.get("data", [])
            return {
                "status": data.get("status", "success"),
                "pattern_count": len(patterns),
                "patterns": [
                    {
                        "pattern": p.get("pattern", ""),
                        "total_samples": sum(s[1] for s in p.get("samples", [])),
                        "sample_count": len(p.get("samples", [])),
                    }
                    for p in patterns
                ],
            }

    @mcp.tool()
    async def loki_stats(
        query: str,
        start: str,
        end: str,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get quick statistics about logs matching a query.

        Returns approximate counts of streams, chunks, entries, and bytes
        without fetching actual log content. Use this to understand query
        scope before fetching logs.

        Args:
            query: LogQL matchers (e.g., '{app="myapp", env!="dev"}')
            start: Start timestamp (Unix epoch seconds or RFC3339)
            end: End timestamp (Unix epoch seconds or RFC3339)
            instance: LGTM instance name

        Returns:
            Dictionary with streams, chunks, entries, and bytes counts
        """
        async with get_loki_client(instance) as client:
            return await client.get_index_stats(query, start, end)

    @mcp.tool()
    async def loki_volume(
        query: str,
        start: str,
        end: str,
        limit: int = 100,
        target_labels: str | None = None,
        aggregate_by: str = "series",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Get log volume breakdown by labels.

        Shows how much log data exists for different label combinations.
        Useful for identifying high-volume log sources.

        Args:
            query: LogQL stream selector (e.g., '{app=~".+"}')
            start: Start timestamp (Unix epoch seconds or RFC3339)
            end: End timestamp (Unix epoch seconds or RFC3339)
            limit: Maximum series to return (default: 100)
            target_labels: Comma-separated labels to aggregate by (e.g., "app,env")
            aggregate_by: "series" for label combinations, "labels" for label names only
            instance: LGTM instance name

        Returns:
            Dictionary with volume data per label combination
        """
        async with get_loki_client(instance) as client:
            return await client.get_volume(query, start, end, limit, target_labels, aggregate_by)

    @mcp.tool()
    async def loki_query_logs(
        query: str,
        start: str,
        end: str,
        limit: int = 20,
        direction: str = "backward",
        max_line_length: int = 500,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve log entries. Use loki_patterns first to understand log structure.

        Fetches actual log lines matching a query. For initial investigation,
        use loki_patterns to identify interesting patterns, then use this
        to get specific examples.

        Args:
            query: LogQL query string (e.g., '{app="myapp"} |= "error"')
            start: Start timestamp (Unix epoch seconds or RFC3339)
            end: End timestamp (Unix epoch seconds or RFC3339)
            limit: Maximum log entries to return (default: 20)
            direction: Query direction - "backward" (newest first) or "forward"
            max_line_length: Truncate log lines longer than this (default: 500)
            instance: LGTM instance name (uses default if not specified)

        Returns:
            Dictionary with log entries containing timestamp, labels, and line
        """
        async with get_loki_client(instance) as client:
            response = await client.query_range(query, start, end, limit, direction)
            entries = response.get_log_entries()[:limit]
            for entry in entries:
                line = entry.get("line", "")
                if len(line) > max_line_length:
                    entry["line"] = line[:max_line_length] + "..."
                    entry["truncated"] = True
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "entries": entries,
                "count": len(entries),
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
