"""Tempo API client."""

from typing import Any

import httpx

from lgtm_mcp.clients.base import BaseClient
from lgtm_mcp.models.config import BackendConfig, Settings
from lgtm_mcp.models.tempo import (
    TempoSearchResponse,
    TempoTagsResponse,
    TempoTagValuesResponse,
)
from lgtm_mcp.tracing import traced_operation


class TempoClient(BaseClient):
    """Client for Tempo HTTP API."""

    def __init__(
        self,
        config: BackendConfig,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        instance_name: str = "unknown",
    ):
        super().__init__(config, settings, http_client, instance_name, "tempo")

    @traced_operation(query_param="trace_id")
    async def get_trace(
        self,
        trace_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        """Get a trace by ID.

        Args:
            trace_id: The trace ID to retrieve
            start: Start timestamp to narrow search
            end: End timestamp to narrow search

        Returns:
            Trace data in OTLP JSON format
        """
        params = {"start": start, "end": end}
        data = await self._get(f"/api/traces/{trace_id}", params=params)
        return data

    @traced_operation()
    async def search(
        self,
        query: str | None = None,
        tags: dict[str, str] | None = None,
        min_duration: str | None = None,
        max_duration: str | None = None,
        limit: int = 20,
        start: str | None = None,
        end: str | None = None,
    ) -> TempoSearchResponse:
        """Search traces with TraceQL or tags.

        Args:
            query: TraceQL query string
            tags: Tag key-value pairs for filtering
            min_duration: Minimum trace duration (e.g., "100ms")
            max_duration: Maximum trace duration
            limit: Maximum traces to return
            start: Start timestamp
            end: End timestamp

        Returns:
            TempoSearchResponse with matching traces
        """
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if tags:
            params["tags"] = " ".join(f'{k}="{v}"' for k, v in tags.items())
        if min_duration:
            params["minDuration"] = min_duration
        if max_duration:
            params["maxDuration"] = max_duration
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        data = await self._get("/api/search", params=params)
        return TempoSearchResponse.model_validate(data)

    @traced_operation()
    async def get_tag_names(
        self,
        scope: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[str]:
        """Get available tag names.

        Args:
            scope: Scope to filter tags (span, resource, intrinsic)
            start: Start timestamp
            end: End timestamp

        Returns:
            List of tag names
        """
        params = {"scope": scope, "start": start, "end": end}
        data = await self._get("/api/v2/search/tags", params=params)
        response = TempoTagsResponse.model_validate(data)
        return response.get_all_tags()

    @traced_operation()
    async def get_tag_values(
        self,
        tag: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[str]:
        """Get values for a tag.

        Args:
            tag: Tag name
            start: Start timestamp
            end: End timestamp

        Returns:
            List of tag values
        """
        params = {"start": start, "end": end}
        data = await self._get(f"/api/v2/search/tag/{tag}/values", params=params)
        response = TempoTagValuesResponse.model_validate(data)
        return response.get_values()

    @traced_operation()
    async def get_services(
        self,
        start: str | None = None,
        end: str | None = None,
    ) -> list[str]:
        """Get service names.

        Args:
            start: Start timestamp
            end: End timestamp

        Returns:
            List of service names
        """
        return await self.get_tag_values("service.name", start=start, end=end)
