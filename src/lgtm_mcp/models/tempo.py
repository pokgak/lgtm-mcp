"""Pydantic models for Tempo API responses."""

from typing import Any

from pydantic import BaseModel, Field


class TempoSpan(BaseModel):
    """A single span in a trace."""

    traceID: str = Field(..., description="Trace ID")
    spanID: str = Field(..., description="Span ID")
    operationName: str = Field(..., description="Operation name")
    serviceName: str = Field("", description="Service name")
    startTimeUnixNano: str = Field(..., description="Start time in nanoseconds")
    durationNanos: str = Field(..., description="Duration in nanoseconds")
    tags: list[dict[str, Any]] | None = Field(None, description="Span tags")
    logs: list[dict[str, Any]] | None = Field(None, description="Span logs")
    references: list[dict[str, Any]] | None = Field(None, description="Span references")

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return int(self.durationNanos) / 1_000_000


class TempoResource(BaseModel):
    """Resource information for a batch of spans."""

    serviceName: str = Field("", description="Service name from resource")
    attributes: list[dict[str, Any]] | None = Field(None, description="Resource attributes")


class TempoBatch(BaseModel):
    """A batch of spans from a single resource."""

    resource: TempoResource | None = None
    spans: list[TempoSpan] = Field(default_factory=list)


class TempoTrace(BaseModel):
    """A complete trace with all spans."""

    traceID: str = Field(..., description="Trace ID")
    rootServiceName: str = Field("", description="Root service name")
    rootTraceName: str = Field("", description="Root span name")
    startTimeUnixNano: str = Field(..., description="Trace start time")
    durationMs: float = Field(0, description="Total trace duration in ms")
    spanCount: int = Field(0, description="Number of spans")
    batches: list[TempoBatch] | None = Field(None, description="Span batches by resource")

    def get_all_spans(self) -> list[TempoSpan]:
        """Get all spans from all batches."""
        spans = []
        if self.batches:
            for batch in self.batches:
                spans.extend(batch.spans)
        return spans


class TempoTraceResponse(BaseModel):
    """Tempo trace by ID response (OTLP format wrapper)."""

    batches: list[dict[str, Any]] = Field(default_factory=list)


class TempoSearchResult(BaseModel):
    """A single trace in search results."""

    traceID: str = Field(..., description="Trace ID")
    rootServiceName: str = Field("", description="Root service name")
    rootTraceName: str = Field("", description="Root span/trace name")
    startTimeUnixNano: str = Field(..., description="Start time in nanoseconds")
    durationMs: float = Field(0, description="Duration in milliseconds")
    spanCount: int | None = Field(None, description="Number of spans")
    spanSet: dict[str, Any] | None = Field(None, description="Matched spans (TraceQL)")


class TempoSearchResponse(BaseModel):
    """Tempo search API response."""

    traces: list[TempoSearchResult] = Field(default_factory=list)
    metrics: dict[str, Any] | None = Field(None, description="Search metrics")


class TempoTagScope(BaseModel):
    """A scope containing tags."""

    name: str = Field(..., description="Scope name (e.g., span, resource)")
    tags: list[str] = Field(default_factory=list, description="Tag names in this scope")


class TempoTagsResponse(BaseModel):
    """Tempo tags API v2 response."""

    scopes: list[TempoTagScope] = Field(default_factory=list)

    def get_all_tags(self) -> list[str]:
        """Get all tags from all scopes."""
        tags = []
        for scope in self.scopes:
            tags.extend(scope.tags)
        return tags


class TempoTagValue(BaseModel):
    """A tag value."""

    value: str = Field(..., description="Tag value")
    type: str = Field("string", description="Value type")


class TempoTagValuesResponse(BaseModel):
    """Tempo tag values API response."""

    tagValues: list[TempoTagValue] = Field(default_factory=list)

    def get_values(self) -> list[str]:
        """Get just the value strings."""
        return [tv.value for tv in self.tagValues]
