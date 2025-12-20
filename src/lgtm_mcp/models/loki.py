"""Pydantic models for Loki API responses."""

from typing import Any

from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """A single log entry with timestamp and line."""

    timestamp: str = Field(..., description="Timestamp in nanoseconds")
    line: str = Field(..., description="Log line content")


class LokiStream(BaseModel):
    """A stream of log entries with labels."""

    stream: dict[str, str] = Field(..., description="Stream labels")
    values: list[list[str]] = Field(..., description="List of [timestamp, line] pairs")

    def to_entries(self) -> list[LogEntry]:
        """Convert values to LogEntry objects."""
        return [LogEntry(timestamp=ts, line=line) for ts, line in self.values]


class LokiMatrixValue(BaseModel):
    """A matrix result value (for metric queries)."""

    metric: dict[str, str] = Field(..., description="Metric labels")
    values: list[list[Any]] = Field(..., description="List of [timestamp, value] pairs")


class LokiQueryData(BaseModel):
    """Data portion of Loki query response."""

    resultType: str = Field(..., description="Result type: streams, matrix, vector, scalar")
    result: list[LokiStream] | list[LokiMatrixValue] | list[Any] = Field(
        ..., description="Query results"
    )


class LokiQueryResponse(BaseModel):
    """Loki query API response."""

    status: str = Field(..., description="Response status")
    data: LokiQueryData = Field(..., description="Query data")

    def get_log_entries(self) -> list[dict[str, Any]]:
        """Extract log entries from streams result."""
        entries = []
        if self.data.resultType == "streams":
            for stream in self.data.result:
                if isinstance(stream, LokiStream):
                    labels = stream.stream
                    for ts, line in stream.values:
                        entries.append({"timestamp": ts, "labels": labels, "line": line})
                elif isinstance(stream, dict) and "stream" in stream and "values" in stream:
                    labels = stream["stream"]
                    for ts, line in stream["values"]:
                        entries.append({"timestamp": ts, "labels": labels, "line": line})
        return entries


class LokiLabelsResponse(BaseModel):
    """Loki labels API response."""

    status: str
    data: list[str]


class LokiSeriesResponse(BaseModel):
    """Loki series API response."""

    status: str
    data: list[dict[str, str]]
