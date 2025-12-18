"""Loki API client."""

import httpx

from lgtm_mcp.clients.base import BaseClient
from lgtm_mcp.models.config import BackendConfig, Settings
from lgtm_mcp.models.loki import (
    LokiLabelsResponse,
    LokiQueryResponse,
    LokiSeriesResponse,
)
from lgtm_mcp.tracing import traced_operation


class LokiClient(BaseClient):
    """Client for Loki HTTP API."""

    def __init__(
        self,
        config: BackendConfig,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        instance_name: str = "unknown",
    ):
        super().__init__(config, settings, http_client, instance_name, "loki")

    @traced_operation()
    async def query_range(
        self,
        query: str,
        start: str,
        end: str,
        limit: int = 100,
        direction: str = "backward",
    ) -> LokiQueryResponse:
        """Query logs over a time range.

        Args:
            query: LogQL query string
            start: Start timestamp (Unix epoch or RFC3339)
            end: End timestamp (Unix epoch or RFC3339)
            limit: Maximum number of entries to return
            direction: Query direction (backward or forward)

        Returns:
            LokiQueryResponse with log streams
        """
        params = {
            "query": query,
            "start": start,
            "end": end,
            "limit": limit,
            "direction": direction,
        }
        data = await self._get("/loki/api/v1/query_range", params=params)
        return LokiQueryResponse.model_validate(data)

    @traced_operation()
    async def instant_query(
        self,
        query: str,
        time: str | None = None,
        limit: int = 100,
    ) -> LokiQueryResponse:
        """Execute instant query (for metric-type LogQL).

        Args:
            query: LogQL query string (e.g., count_over_time)
            time: Evaluation timestamp
            limit: Maximum number of entries

        Returns:
            LokiQueryResponse with vector/matrix result
        """
        params = {"query": query, "limit": limit, "time": time}
        data = await self._get("/loki/api/v1/query", params=params)
        return LokiQueryResponse.model_validate(data)

    @traced_operation()
    async def get_labels(
        self,
        start: str | None = None,
        end: str | None = None,
        query: str | None = None,
    ) -> list[str]:
        """Get known label names.

        Args:
            start: Start timestamp for filtering
            end: End timestamp for filtering
            query: LogQL query to scope labels

        Returns:
            List of label names
        """
        params = {"start": start, "end": end, "query": query}
        data = await self._get("/loki/api/v1/labels", params=params)
        response = LokiLabelsResponse.model_validate(data)
        return response.data

    @traced_operation()
    async def get_label_values(
        self,
        label: str,
        start: str | None = None,
        end: str | None = None,
        query: str | None = None,
    ) -> list[str]:
        """Get values for a specific label.

        Args:
            label: Label name
            start: Start timestamp for filtering
            end: End timestamp for filtering
            query: LogQL query to scope values

        Returns:
            List of label values
        """
        params = {"start": start, "end": end, "query": query}
        data = await self._get(f"/loki/api/v1/label/{label}/values", params=params)
        response = LokiLabelsResponse.model_validate(data)
        return response.data

    @traced_operation()
    async def get_series(
        self,
        match: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, str]]:
        """Find streams matching label selectors.

        Args:
            match: List of label selector strings (e.g., ['{app="foo"}'])
            start: Start timestamp
            end: End timestamp

        Returns:
            List of label sets for matching streams
        """
        params: dict = {"match[]": match, "start": start, "end": end}
        data = await self._get("/loki/api/v1/series", params=params)
        response = LokiSeriesResponse.model_validate(data)
        return response.data
