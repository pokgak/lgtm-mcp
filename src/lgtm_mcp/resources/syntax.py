"""MCP resources for query language syntax documentation."""

from mcp.server.fastmcp import FastMCP

LOGQL_SYNTAX = """# LogQL Syntax Reference

## Log Stream Selectors
Select log streams by labels:
- `{app="myapp"}` - exact match
- `{app=~"my.*"}` - regex match
- `{app!="myapp"}` - not equal
- `{app!~"my.*"}` - regex not match

## Line Filters
Filter log lines (applied after stream selection):
- `|= "error"` - line contains "error"
- `!= "debug"` - line does not contain
- `|~ "error|warn"` - regex match
- `!~ "debug|trace"` - regex not match

## Parser Expressions
Parse structured logs:
- `| json` - parse JSON logs
- `| logfmt` - parse logfmt logs
- `| pattern "<pattern>"` - parse with pattern
- `| regexp "<regex>"` - parse with regex

## Label Filters (after parsing)
- `| level="error"` - filter by extracted label
- `| status >= 400` - numeric comparison
- `| latency > 1s` - duration comparison

## Metric Queries
Aggregate logs into metrics:
- `count_over_time({app="myapp"}[5m])` - count logs in window
- `rate({app="myapp"}[5m])` - rate of logs per second
- `bytes_over_time({app="myapp"}[5m])` - bytes in window
- `bytes_rate({app="myapp"}[5m])` - bytes per second

## Aggregation Operators
- `sum by (label) (...)` - sum grouped by label
- `avg by (label) (...)` - average grouped by label
- `max by (label) (...)` - maximum grouped by label
- `topk(10, ...)` - top 10 results

## Examples
```logql
# Find errors in myapp
{app="myapp"} |= "error"

# Parse JSON and filter by level
{app="myapp"} | json | level="error"

# Count errors per minute by service
sum by (service) (count_over_time({level="error"}[1m]))

# Find slow requests
{app="api"} | json | latency > 1s
```
"""

PROMQL_SYNTAX = """# PromQL Syntax Reference

## Selectors
Select time series by metric name and labels:
- `http_requests_total` - metric name
- `http_requests_total{job="api"}` - with label filter
- `http_requests_total{job=~"api.*"}` - regex match
- `{__name__=~"http.*"}` - match metric names

## Range Vectors
Select samples over time:
- `http_requests_total[5m]` - last 5 minutes
- `http_requests_total[1h]` - last 1 hour

## Instant Vector Functions
- `rate(metric[5m])` - per-second rate
- `irate(metric[5m])` - instant rate (last 2 points)
- `increase(metric[5m])` - total increase
- `delta(metric[5m])` - difference (gauges)
- `deriv(metric[5m])` - derivative (gauges)

## Aggregation Operators
- `sum(metric)` - sum all series
- `sum by (label) (metric)` - sum grouped by label
- `sum without (label) (metric)` - sum excluding label
- `avg`, `min`, `max`, `count`, `stddev`, `stdvar`
- `topk(10, metric)` - top 10 series
- `bottomk(10, metric)` - bottom 10 series
- `quantile(0.95, metric)` - 95th percentile

## Binary Operators
- `metric1 + metric2` - addition
- `metric1 - metric2` - subtraction
- `metric1 * metric2` - multiplication
- `metric1 / metric2` - division
- `metric1 > 100` - comparison (returns 1/0)
- `metric1 and metric2` - intersection
- `metric1 or metric2` - union

## Label Manipulation
- `label_replace(metric, "dst", "$1", "src", "regex")` - replace label
- `label_join(metric, "dst", ",", "src1", "src2")` - join labels

## Examples
```promql
# Request rate per second
rate(http_requests_total[5m])

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m]))
/ sum(rate(http_requests_total[5m])) * 100

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Top 10 endpoints by request count
topk(10, sum by (endpoint) (rate(http_requests_total[5m])))
```
"""

TRACEQL_SYNTAX = """# TraceQL Syntax Reference

## Span Selectors
Select spans by attributes:
- `{resource.service.name="myapp"}` - resource attribute
- `{span.http.method="GET"}` - span attribute
- `{name="HTTP GET"}` - span name (intrinsic)
- `{status=error}` - span status (intrinsic)

## Intrinsic Attributes
Built-in span properties:
- `name` - span name
- `status` - ok, error, unset
- `duration` - span duration
- `kind` - client, server, producer, consumer, internal
- `traceDuration` - total trace duration
- `rootName` - root span name
- `rootServiceName` - root service name

## Comparison Operators
- `=` - equals
- `!=` - not equals
- `=~` - regex match
- `!~` - regex not match
- `>`, `>=`, `<`, `<=` - numeric comparison

## Duration Filters
- `{duration > 100ms}` - spans longer than 100ms
- `{duration >= 1s}` - spans 1 second or longer
- `{traceDuration > 5s}` - traces longer than 5s

## Combining Conditions
- `{condition1 && condition2}` - AND
- `{condition1 || condition2}` - OR
- `{condition1} && {condition2}` - spans match first AND trace has span matching second

## Structural Operators
- `{ } >> { }` - ancestor/descendant (parent >> child)
- `{ } > { }` - direct parent/child
- `{ } ~ { }` - sibling spans
- `{ } !>> { }` - not ancestor (negation)

## Aggregations
- `count()` - count matching spans
- `avg(duration)` - average duration
- `max(duration)` - max duration
- `min(duration)` - min duration
- `sum(duration)` - sum of durations

## Examples
```traceql
# Find all spans for a service
{resource.service.name="myapp"}

# Find error spans
{status=error}

# Find slow HTTP requests
{span.http.method="GET" && duration > 500ms}

# Find traces where API calls database
{resource.service.name="api"} >> {resource.service.name="database"}

# Find traces with errors in payment service
{resource.service.name="payment" && status=error}

# Count spans by service
{} | count() by (resource.service.name)
```
"""


def register_syntax_resources(mcp: FastMCP) -> None:
    """Register query syntax documentation resources."""

    @mcp.resource("lgtm://syntax/logql")
    async def logql_syntax() -> str:
        """LogQL syntax reference for Loki queries.

        Returns markdown documentation of LogQL syntax including
        selectors, filters, parsers, and metric queries.
        """
        return LOGQL_SYNTAX

    @mcp.resource("lgtm://syntax/promql")
    async def promql_syntax() -> str:
        """PromQL syntax reference for Prometheus queries.

        Returns markdown documentation of PromQL syntax including
        selectors, functions, operators, and aggregations.
        """
        return PROMQL_SYNTAX

    @mcp.resource("lgtm://syntax/traceql")
    async def traceql_syntax() -> str:
        """TraceQL syntax reference for Tempo queries.

        Returns markdown documentation of TraceQL syntax including
        span selectors, intrinsics, structural operators, and aggregations.
        """
        return TRACEQL_SYNTAX
