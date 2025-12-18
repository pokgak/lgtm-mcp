"""Prometheus API client."""

from lgtm_mcp.clients.base import BaseClient
from lgtm_mcp.models.prometheus import (
    PrometheusLabelsResponse,
    PrometheusMetadataResponse,
    PrometheusQueryResponse,
    PrometheusSeriesResponse,
)


class PrometheusClient(BaseClient):
    """Client for Prometheus HTTP API."""

    async def instant_query(
        self,
        query: str,
        time: str | None = None,
    ) -> PrometheusQueryResponse:
        """Execute instant query.

        Args:
            query: PromQL query string
            time: Evaluation timestamp

        Returns:
            PrometheusQueryResponse with vector result
        """
        params = {"query": query, "time": time}
        data = await self._get("/api/v1/query", params=params)
        return PrometheusQueryResponse.model_validate(data)

    async def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "1m",
    ) -> PrometheusQueryResponse:
        """Execute range query.

        Args:
            query: PromQL query string
            start: Start timestamp
            end: End timestamp
            step: Query resolution step (e.g., "1m", "5m")

        Returns:
            PrometheusQueryResponse with matrix result
        """
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        data = await self._get("/api/v1/query_range", params=params)
        return PrometheusQueryResponse.model_validate(data)

    async def get_label_names(
        self,
        match: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[str]:
        """Get label names.

        Args:
            match: Series selector(s) to filter labels
            start: Start timestamp
            end: End timestamp

        Returns:
            List of label names
        """
        params: dict = {"start": start, "end": end}
        if match:
            params["match[]"] = match
        data = await self._get("/api/v1/labels", params=params)
        response = PrometheusLabelsResponse.model_validate(data)
        return response.data

    async def get_label_values(
        self,
        label: str,
        match: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[str]:
        """Get values for a label.

        Args:
            label: Label name
            match: Series selector(s) to filter values
            start: Start timestamp
            end: End timestamp

        Returns:
            List of label values
        """
        params: dict = {"start": start, "end": end}
        if match:
            params["match[]"] = match
        data = await self._get(f"/api/v1/label/{label}/values", params=params)
        response = PrometheusLabelsResponse.model_validate(data)
        return response.data

    async def get_series(
        self,
        match: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, str]]:
        """Find series matching selectors.

        Args:
            match: Series selector(s)
            start: Start timestamp
            end: End timestamp

        Returns:
            List of label sets for matching series
        """
        params: dict = {"match[]": match, "start": start, "end": end}
        data = await self._get("/api/v1/series", params=params)
        response = PrometheusSeriesResponse.model_validate(data)
        return response.data

    async def get_metric_names(
        self,
        match: str | None = None,
    ) -> list[str]:
        """Get metric names.

        Args:
            match: Optional series selector to filter metrics

        Returns:
            List of metric names
        """
        params: dict = {}
        if match:
            params["match[]"] = [match]
        data = await self._get("/api/v1/label/__name__/values", params=params)
        response = PrometheusLabelsResponse.model_validate(data)
        return response.data

    async def get_metadata(
        self,
        metric: str | None = None,
        limit: int | None = None,
    ) -> dict[str, list[dict]]:
        """Get metric metadata.

        Args:
            metric: Optional metric name to filter
            limit: Maximum metadata entries

        Returns:
            Dict mapping metric names to metadata entries
        """
        params = {"metric": metric, "limit": limit}
        data = await self._get("/api/v1/metadata", params=params)
        response = PrometheusMetadataResponse.model_validate(data)
        return {name: [m.model_dump() for m in metas] for name, metas in response.data.items()}
