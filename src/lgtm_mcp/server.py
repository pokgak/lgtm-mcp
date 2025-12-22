"""LGTM MCP Server - Read-only access to Loki, Prometheus, and Tempo APIs."""

import asyncio
from typing import Any, Literal

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
from lgtm_mcp.tracing import init_tracing

mcp = FastMCP(
    "LGTM MCP Server",
)


def register_tools_dynamically(mcp: FastMCP) -> None:
    """Register only tools for backends that are configured."""
    config = load_config()

    has_loki = False
    has_prometheus = False
    has_tempo = False

    for instance in config.instances.values():
        if instance.loki:
            has_loki = True
        if instance.prometheus:
            has_prometheus = True
        if instance.tempo:
            has_tempo = True

    if has_loki:
        register_loki_tools(mcp)
    if has_prometheus:
        register_prometheus_tools(mcp)
    if has_tempo:
        register_tempo_tools(mcp)


@mcp.tool()
def instances(
    action: Literal["list", "set_default"] = "list",
    name: str | None = None,
) -> dict[str, Any]:
    """Manage LGTM instances: list available instances or set default.

    Args:
        action: "list" to show instances, "set_default" to change default
        name: Instance name (required for set_default)
    """
    manager = get_instance_manager()

    if action == "list":
        return {"status": "success", "instances": manager.list_instances()}

    elif action == "set_default":
        if not name:
            return {"status": "error", "message": "name parameter required for set_default"}
        manager.set_default(name)
        return {"status": "success", "message": f"Default instance set to: {name}"}

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


register_tools_dynamically(mcp)
register_label_resources(mcp)
register_metric_resources(mcp)
register_syntax_resources(mcp)


def main() -> None:
    """Main entry point for the MCP server."""
    init_tracing()
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
