# LGTM MCP Server

MCP server providing read-only access to Loki, Prometheus, and Tempo APIs.

## Features

- **Multi-instance support**: Configure multiple LGTM stacks and switch between them
- **Bearer token authentication**: Works with Grafana Cloud and self-hosted deployments
- **Query tools**: Execute LogQL, PromQL, and TraceQL queries
- **Metadata discovery**: Expose labels, metrics, and tags as MCP resources
- **Syntax documentation**: Built-in query language references
- **OpenTelemetry tracing**: All HTTP client calls are traced and exported via OTLP/gRPC

## Configuration

Create a config file at `~/.config/lgtm-mcp/config.yaml`:

```yaml
version: "1"
default_instance: "local"

instances:
  local:
    loki:
      url: "http://localhost:3100"
    prometheus:
      url: "http://localhost:9090"
    tempo:
      url: "http://localhost:3200"

  grafana-cloud:
    loki:
      url: "https://logs-prod-us-west-0.grafana.net"
      username: "${GRAFANA_CLOUD_LOKI_USERNAME}"
      token: "${GRAFANA_CLOUD_TOKEN}"
    prometheus:
      url: "https://prometheus-prod-01-us-west-0.grafana.net/api/prom"
      username: "${GRAFANA_CLOUD_PROMETHEUS_USERNAME}"
      token: "${GRAFANA_CLOUD_TOKEN}"
    tempo:
      url: "https://tempo-prod-us-west-0.grafana.net"
      username: "${GRAFANA_CLOUD_TEMPO_USERNAME}"
      token: "${GRAFANA_CLOUD_TOKEN}"
```

Environment variables are expanded using `${VAR}` syntax.

For Grafana Cloud, a token with read-only permissions is sufficient. See [Creating access policies](https://grafana.com/docs/grafana-cloud/security-and-account-management/authentication-and-permissions/access-policies/create-access-policies/) for details.

## Usage

### Claude Code

Add the MCP server using the Claude Code CLI:

```bash
claude mcp add lgtm -- uvx --from git+https://github.com/pokgak/lgtm-mcp lgtm-mcp
```

Or manually add to your Claude Code MCP settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "lgtm": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/pokgak/lgtm-mcp", "lgtm-mcp"]
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "lgtm": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/pokgak/lgtm-mcp", "lgtm-mcp"]
    }
  }
}
```

### Local Development

If you've cloned the repository locally:

```json
{
  "mcpServers": {
    "lgtm": {
      "command": "uv",
      "args": ["run", "lgtm-mcp"],
      "cwd": "/path/to/lgtm-mcp"
    }
  }
}
```

### Available Tools

**Loki (Logs)**
- `loki_query_logs` - Execute LogQL queries
- `loki_instant_query` - Metric-type LogQL at single point
- `loki_get_labels` - List label names
- `loki_get_label_values` - Get values for a label
- `loki_get_series` - Find matching log streams

**Prometheus (Metrics)**
- `prometheus_instant_query` - Execute PromQL instant query
- `prometheus_range_query` - Execute PromQL range query (**broken**)
- `prometheus_get_metric_names` - List metrics
- `prometheus_get_label_names` - List label names
- `prometheus_get_label_values` - Get values for a label
- `prometheus_get_series` - Find matching series
- `prometheus_get_metadata` - Get metric metadata

**Tempo (Traces)**
- `tempo_get_trace` - Retrieve trace by ID
- `tempo_search_traces` - Search with TraceQL
- `tempo_get_tag_names` - List tag names
- `tempo_get_tag_values` - Get values for a tag
- `tempo_get_services` - List service names

**Utility**
- `list_instances` - List configured instances
- `set_default_instance` - Change default instance

### Available Resources

Resources expose metadata for query generation:

- `lgtm://{instance}/loki/labels` - Loki label names
- `lgtm://{instance}/prometheus/labels` - Prometheus label names
- `lgtm://{instance}/prometheus/metrics` - Metric names
- `lgtm://{instance}/tempo/tags` - Tempo tag names
- `lgtm://syntax/logql` - LogQL syntax reference
- `lgtm://syntax/promql` - PromQL syntax reference
- `lgtm://syntax/traceql` - TraceQL syntax reference

## Tracing

The server automatically instruments all HTTP client calls with OpenTelemetry. Traces are exported via OTLP/gRPC.

By default, traces are sent to `http://localhost:4317`. Override with:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://your-collector:4317"
```

Service name: `lgtm-mcp`

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run type checks
mypy src/

# Run linter
ruff check src/

# Run tests
pytest
```
