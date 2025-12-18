"""MCP tools for LGTM backends."""

from lgtm_mcp.tools.loki import register_loki_tools
from lgtm_mcp.tools.prometheus import register_prometheus_tools
from lgtm_mcp.tools.tempo import register_tempo_tools

__all__ = [
    "register_loki_tools",
    "register_prometheus_tools",
    "register_tempo_tools",
]
