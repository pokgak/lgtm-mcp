"""Tempo MCP tools for trace querying."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.clients.tempo import TempoClient
from lgtm_mcp.config import get_instance_manager, load_config


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
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a trace by its ID.

        Args:
            trace_id: The trace ID to retrieve (hex string)
            start: Start timestamp to narrow search window
            end: End timestamp to narrow search window
            instance: LGTM instance name

        Returns:
            Trace data in OTLP JSON format
        """
        async with get_tempo_client(instance) as client:
            return await client.get_trace(trace_id, start, end)

    @mcp.tool()
    async def tempo_search_traces(
        query: str | None = None,
        tags: dict[str, str] | None = None,
        min_duration: str | None = None,
        max_duration: str | None = None,
        limit: int = 20,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Search traces with TraceQL or tag filters.

        Args:
            query: TraceQL query string (e.g., '{resource.service.name="myapp"}')
            tags: Tag key-value pairs for filtering (legacy API)
            min_duration: Minimum trace duration (e.g., "100ms", "1s")
            max_duration: Maximum trace duration
            limit: Maximum traces to return (default: 20)
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            Dictionary with matching traces
        """
        async with get_tempo_client(instance) as client:
            response = await client.search(
                query, tags, min_duration, max_duration, limit, start, end
            )
            return {
                "traces": [t.model_dump() for t in response.traces],
                "count": len(response.traces),
                "metrics": response.metrics,
            }

    @mcp.tool()
    async def tempo_get_tag_names(
        scope: str | None = None,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """List available tag names in Tempo.

        Args:
            scope: Scope to filter tags (span, resource, intrinsic)
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of tag names
        """
        async with get_tempo_client(instance) as client:
            return await client.get_tag_names(scope, start, end)

    @mcp.tool()
    async def tempo_get_tag_values(
        tag: str,
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """Get values for a specific tag in Tempo.

        Args:
            tag: Tag name (e.g., "service.name", "http.status_code")
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of tag values
        """
        async with get_tempo_client(instance) as client:
            return await client.get_tag_values(tag, start, end)

    @mcp.tool()
    async def tempo_get_services(
        start: str | None = None,
        end: str | None = None,
        instance: str | None = None,
    ) -> list[str]:
        """List service names from traces.

        Args:
            start: Start timestamp
            end: End timestamp
            instance: LGTM instance name

        Returns:
            List of service names
        """
        async with get_tempo_client(instance) as client:
            return await client.get_services(start, end)
