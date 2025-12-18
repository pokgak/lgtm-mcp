# LGTM MCP Server Implementation Plan

## Overview
Python MCP server providing read-only access to Loki, Prometheus, and Tempo APIs with support for multiple instances and bearer token authentication.

## Project Structure
```
lgtm-proxy/
├── pyproject.toml
├── config.example.yaml
├── src/lgtm_mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP entry point
│   ├── config.py              # YAML config loading
│   ├── models/
│   │   ├── __init__.py
│   │   ├── config.py          # Config Pydantic models
│   │   ├── loki.py            # Loki response models
│   │   ├── prometheus.py      # Prometheus response models
│   │   └── tempo.py           # Tempo response models
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── base.py            # Base HTTP client (auth, errors, pooling)
│   │   ├── loki.py            # Loki API client
│   │   ├── prometheus.py      # Prometheus API client
│   │   └── tempo.py           # Tempo API client
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── loki.py            # Loki MCP tools
│   │   ├── prometheus.py      # Prometheus MCP tools
│   │   └── tempo.py           # Tempo MCP tools
│   └── resources/
│       ├── __init__.py
│       ├── labels.py          # Label name/value resources
│       ├── metrics.py         # Metric metadata resources
│       └── syntax.py          # Query language syntax docs
└── tests/
```

## Config Schema (config.yaml)
```yaml
version: "1"
default_instance: "production"

instances:
  production:
    loki:
      url: "https://logs-prod.grafana.net"
      token: "${LOKI_TOKEN}"      # Env var expansion
      timeout: 30
    prometheus:
      url: "https://prometheus-prod.grafana.net"
      token: "${PROMETHEUS_TOKEN}"
      timeout: 30
    tempo:
      url: "https://tempo-prod.grafana.net"
      token: "${TEMPO_TOKEN}"
      timeout: 60

settings:
  max_log_entries: 1000
  max_metric_samples: 10000
  max_traces: 100
```

Config path: `~/.config/lgtm-mcp/config.yaml` or `LGTM_MCP_CONFIG` env var.

## MCP Tools

### Loki (5 tools)
| Tool | Purpose |
|------|---------|
| `loki_query_logs` | Execute LogQL query over time range |
| `loki_instant_query` | Execute metric-type LogQL at single point |
| `loki_get_labels` | List all known label names |
| `loki_get_label_values` | Get values for a specific label |
| `loki_get_series` | Find streams matching label selectors |

### Prometheus (7 tools)
| Tool | Purpose |
|------|---------|
| `prometheus_instant_query` | Execute PromQL instant query |
| `prometheus_range_query` | Execute PromQL range query |
| `prometheus_get_metric_names` | List metric names |
| `prometheus_get_label_names` | List label names |
| `prometheus_get_label_values` | Get values for a label |
| `prometheus_get_series` | Find series matching selectors |
| `prometheus_get_metadata` | Get metric metadata (type, help, unit) |

### Tempo (5 tools)
| Tool | Purpose |
|------|---------|
| `tempo_get_trace` | Retrieve trace by ID |
| `tempo_search_traces` | Search traces with TraceQL or tags |
| `tempo_get_tag_names` | List available tag names |
| `tempo_get_tag_values` | Get values for a tag |
| `tempo_get_services` | List service names |

### Utility (2 tools)
| Tool | Purpose |
|------|---------|
| `list_instances` | List configured LGTM instances |
| `set_default_instance` | Change default instance for session |

## MCP Resources (Discovery)

Resources expose deployment-specific metadata so LLMs can generate accurate queries without hallucinating label names or invalid syntax. **Tools handle execution, Resources handle discovery.**

### Label Resources
| URI Pattern | Description |
|-------------|-------------|
| `lgtm://{instance}/loki/labels` | All Loki label names |
| `lgtm://{instance}/loki/labels/{label}/values` | Values for a Loki label (paginated) |
| `lgtm://{instance}/prometheus/labels` | All Prometheus label names |
| `lgtm://{instance}/prometheus/labels/{label}/values` | Values for a Prometheus label (paginated) |
| `lgtm://{instance}/tempo/tags` | All Tempo tag names |
| `lgtm://{instance}/tempo/tags/{tag}/values` | Values for a Tempo tag |

### Metric Resources
| URI Pattern | Description |
|-------------|-------------|
| `lgtm://{instance}/prometheus/metrics` | List of all metric names |
| `lgtm://{instance}/prometheus/metrics/{name}` | Metadata for a specific metric (type, help, unit) |

### Query Syntax Resources (Static)
| URI Pattern | Description |
|-------------|-------------|
| `lgtm://syntax/logql` | LogQL syntax reference (functions, operators, parsers) |
| `lgtm://syntax/promql` | PromQL syntax reference (functions, aggregations, operators) |
| `lgtm://syntax/traceql` | TraceQL syntax reference (intrinsics, operators) |

### Resource Design Notes
- **Pagination**: High-cardinality labels (e.g., `pod`, `trace_id`) return paginated results (max 1000)
- **Caching**: Resources can be cached client-side
- **Resource templates**: Use MCP resource templates for parameterized URIs

## Dependencies
```toml
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    "pyyaml>=6.0",
]
```

## Key Design Decisions

1. **httpx for HTTP**: Async client with built-in connection pooling
2. **Pydantic for validation**: Config and response models
3. **FastMCP**: Simplified MCP server creation with decorators
4. **Environment variable expansion**: `${VAR}` syntax in YAML for secrets
5. **Instance parameter on all tools**: Optional, falls back to default instance
6. **Structured responses**: All tools return Pydantic models for consistent output
7. **Tools vs Resources separation**: Tools execute queries, Resources expose discoverable metadata
8. **Pagination for high-cardinality**: Labels like `pod`, `trace_id` limited to 1000 values
9. **Static syntax docs**: Query language references bundled as markdown resources

## Critical Files
- `src/lgtm_mcp/server.py` - Main entry point
- `src/lgtm_mcp/clients/base.py` - Base HTTP client pattern
- `src/lgtm_mcp/config.py` - Config loading logic
- `src/lgtm_mcp/resources/labels.py` - Resource templates for label discovery
- `src/lgtm_mcp/resources/syntax.py` - Static query syntax documentation
- `pyproject.toml` - Project setup

## Usage

### Installation
```bash
uv pip install -e .
```

### Running
```bash
uv run lgtm-mcp
```

### Claude Code Integration
Add to `~/.claude.json`:
```json
{
  "mcpServers": {
    "lgtm": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/lgtm-proxy", "lgtm-mcp"]
    }
  }
}
```

## Future Enhancements

- [ ] Rate limiting (client-side token bucket)
- [ ] Caching layer for metadata resources
- [ ] Support for Mimir/Cortex multi-tenancy headers
- [ ] Grafana dashboard link generation
- [ ] Alert rule querying (Prometheus/Mimir)
