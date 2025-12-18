"""Pydantic models for Prometheus API responses."""

from typing import Any

from pydantic import BaseModel, Field


class PrometheusValue(BaseModel):
    """A single instant query result."""

    metric: dict[str, str] = Field(..., description="Metric labels")
    value: list[Any] = Field(..., description="[timestamp, value] pair")


class PrometheusRangeValue(BaseModel):
    """A range query result with multiple values."""

    metric: dict[str, str] = Field(..., description="Metric labels")
    values: list[list[Any]] = Field(..., description="List of [timestamp, value] pairs")


class PrometheusResult(BaseModel):
    """Generic result that can hold either instant or range data."""

    metric: dict[str, str] = Field(default_factory=dict, description="Metric labels")
    value: list[Any] | None = Field(None, description="Instant query value")
    values: list[list[Any]] | None = Field(None, description="Range query values")


class PrometheusQueryData(BaseModel):
    """Data portion of Prometheus query response."""

    resultType: str = Field(..., description="Result type: vector, matrix, scalar, string")
    result: list[PrometheusResult] = Field(..., description="Query results")


class PrometheusQueryResponse(BaseModel):
    """Prometheus query API response."""

    status: str = Field(..., description="Response status")
    data: PrometheusQueryData = Field(..., description="Query data")
    warnings: list[str] | None = Field(None, description="Query warnings")

    def get_instant_values(self) -> list[dict[str, Any]]:
        """Extract instant query values."""
        results = []
        for r in self.data.result:
            if r.value:
                results.append(
                    {
                        "metric": r.metric,
                        "timestamp": r.value[0],
                        "value": r.value[1],
                    }
                )
        return results

    def get_range_values(self) -> list[dict[str, Any]]:
        """Extract range query values."""
        results = []
        for r in self.data.result:
            if r.values:
                results.append(
                    {
                        "metric": r.metric,
                        "values": [{"timestamp": v[0], "value": v[1]} for v in r.values],
                    }
                )
        return results


class PrometheusLabelsResponse(BaseModel):
    """Prometheus labels API response."""

    status: str
    data: list[str]
    warnings: list[str] | None = None


class PrometheusSeriesResponse(BaseModel):
    """Prometheus series API response."""

    status: str
    data: list[dict[str, str]]
    warnings: list[str] | None = None


class PrometheusMetricMetadata(BaseModel):
    """Metadata for a single metric."""

    type: str = Field(..., description="Metric type (counter, gauge, histogram, summary)")
    help: str = Field(..., description="Metric help text")
    unit: str = Field("", description="Metric unit")


class PrometheusMetadataResponse(BaseModel):
    """Prometheus metadata API response."""

    status: str
    data: dict[str, list[PrometheusMetricMetadata]]
