"""MCP resources for LGTM metadata discovery."""

from lgtm_mcp.resources.labels import register_label_resources
from lgtm_mcp.resources.metrics import register_metric_resources
from lgtm_mcp.resources.syntax import register_syntax_resources

__all__ = [
    "register_label_resources",
    "register_metric_resources",
    "register_syntax_resources",
]
