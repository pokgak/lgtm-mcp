"""LGTM MCP Server - Read-only access to Loki, Prometheus, and Tempo APIs."""

import asyncio

from mcp.server.fastmcp import FastMCP

from lgtm_mcp.config import get_instance_manager, load_config
from lgtm_mcp.resources import (
    register_label_resources,
    register_metric_resources,
    register_syntax_resources,
)
from lgtm_mcp.tools import (
    register_loki_tools,
    register_prometheus_tools,
    register_tempo_tools,
)

mcp = FastMCP(
    "LGTM MCP Server",
)


@mcp.tool()
def list_instances() -> list[dict]:
    """List all configured LGTM instances with their available backends."""
    manager = get_instance_manager()
    return manager.list_instances()


@mcp.tool()
def set_default_instance(instance: str) -> str:
    """Set the default instance for subsequent queries.

    Args:
        instance: Name of the instance to set as default

    Returns:
        Confirmation message
    """
    manager = get_instance_manager()
    manager.set_default(instance)
    return f"Default instance set to: {instance}"


register_loki_tools(mcp)
register_prometheus_tools(mcp)
register_tempo_tools(mcp)
register_label_resources(mcp)
register_metric_resources(mcp)
register_syntax_resources(mcp)


def main() -> None:
    """Main entry point for the MCP server."""
    load_config()
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
