"""Token efficiency evaluation runner for lgtm-mcp."""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import tiktoken
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

_encoder: tiktoken.Encoding | None = None


def get_encoder() -> tiktoken.Encoding:
    """Get or create the tiktoken encoder (cached)."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken cl100k_base encoding."""
    return len(get_encoder().encode(text))


@dataclass
class ScenarioResult:
    name: str
    tool: str
    description: str
    tokens: int
    max_tokens: int
    chars: int
    passed: bool
    error: str | None = None
    response: dict = field(default_factory=dict)


def get_time_params() -> dict[str, str]:
    """Get start/end times for queries (last 10 minutes)."""
    now = datetime.now(UTC)
    start = now - timedelta(minutes=10)
    return {
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


async def call_tempo_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call a Tempo tool."""
    from lgtm_mcp.tools.tempo import get_tempo_client

    time_params = get_time_params()

    async with get_tempo_client("local") as client:
        if tool_name == "tempo_search":
            response = await client.search(
                query=params.get("query"),
                tags=None,
                min_duration=params.get("min_duration"),
                max_duration=params.get("max_duration"),
                limit=params.get("limit", 20),
                start=params.get("start", time_params["start"]),
                end=params.get("end", time_params["end"]),
            )
            if not response.traces:
                return {
                    "status": "success",
                    "traces": [],
                    "count": 0,
                    "message": "No traces found.",
                }
            if params.get("include_spans"):
                traces = [t.model_dump() for t in response.traces]
            else:
                traces = [
                    {
                        "traceID": t.traceID,
                        "rootServiceName": t.rootServiceName,
                        "rootTraceName": t.rootTraceName,
                        "startTimeUnixNano": t.startTimeUnixNano,
                        "durationMs": t.durationMs,
                        "spanCount": t.spanSet.get("matched", 0) if t.spanSet else t.spanCount,
                    }
                    for t in response.traces
                ]
            return {"status": "success", "traces": traces, "count": len(traces)}

        elif tool_name == "tempo_metadata":
            info = params.get("info")
            if info == "services":
                services = await client.get_services(
                    params.get("start", time_params["start"]),
                    params.get("end", time_params["end"]),
                )
                return {
                    "status": "success",
                    "services": services or [],
                    "count": len(services or []),
                }
            elif info == "tags":
                tags = await client.get_tag_names(
                    None,
                    params.get("start", time_params["start"]),
                    params.get("end", time_params["end"]),
                )
                return {"status": "success", "tags": tags or [], "count": len(tags or [])}
            elif info == "tag_values":
                tag = params.get("tag")
                if not tag:
                    return {"status": "error", "message": "tag parameter required"}
                values = await client.get_tag_values(
                    tag,
                    params.get("start", time_params["start"]),
                    params.get("end", time_params["end"]),
                )
                return {
                    "status": "success",
                    "tag": tag,
                    "values": values or [],
                    "count": len(values or []),
                }

    return {"status": "error", "message": f"Unknown tempo tool: {tool_name}"}


async def call_loki_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call a Loki tool."""
    from lgtm_mcp.tools.loki import get_loki_client

    time_params = get_time_params()

    async with get_loki_client("local") as client:
        if tool_name == "loki_query":
            response = await client.query_range(
                params["query"],
                params.get("start", time_params["start"]),
                params.get("end", time_params["end"]),
                params.get("limit", 20),
                params.get("direction", "backward"),
            )
            entries = response.get_log_entries()[: params.get("limit", 20)]
            max_line_length = 500
            for entry in entries:
                line = entry.get("line", "")
                if len(line) > max_line_length:
                    entry["line"] = line[:max_line_length] + "..."
                    entry["truncated"] = True
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "entries": entries,
                "count": len(entries),
            }

        elif tool_name == "loki_patterns":
            try:
                data = await client.get_patterns(
                    params["query"],
                    params.get("start", time_params["start"]),
                    params.get("end", time_params["end"]),
                )
                patterns = data.get("data", [])
                return {
                    "status": "success",
                    "pattern_count": len(patterns),
                    "patterns": [
                        {
                            "pattern": p.get("pattern", ""),
                            "total_samples": sum(s[1] for s in p.get("samples", [])),
                        }
                        for p in patterns
                    ],
                }
            except Exception as e:
                if "404" in str(e):
                    return {"status": "error", "error": "patterns_not_available"}
                raise

        elif tool_name == "loki_stats":
            stats = await client.get_index_stats(
                params["query"],
                params.get("start", time_params["start"]),
                params.get("end", time_params["end"]),
            )
            return {"status": "success", "stats": stats}

        elif tool_name == "loki_metadata":
            info = params.get("info")
            if info == "labels":
                labels = await client.get_labels(
                    params.get("start", time_params["start"]),
                    params.get("end", time_params["end"]),
                    params.get("query"),
                )
                return {"status": "success", "labels": labels or [], "count": len(labels or [])}
            elif info == "label_values":
                label = params.get("label")
                if not label:
                    return {"status": "error", "message": "label parameter required"}
                values = await client.get_label_values(
                    label,
                    params.get("start", time_params["start"]),
                    params.get("end", time_params["end"]),
                    params.get("query"),
                )
                return {
                    "status": "success",
                    "label": label,
                    "values": values or [],
                    "count": len(values or []),
                }

    return {"status": "error", "message": f"Unknown loki tool: {tool_name}"}


async def call_prometheus_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call a Prometheus tool."""
    from lgtm_mcp.tools.prometheus import get_prometheus_client

    async with get_prometheus_client("local") as client:
        if tool_name == "prometheus_query":
            start = params.get("start")
            end = params.get("end")
            if start and end:
                response = await client.range_query(
                    params["query"], start, end, params.get("step", "1m")
                )
                result = response.get_range_values()
            else:
                response = await client.instant_query(params["query"], start)
                result = response.get_instant_values()
            return {
                "status": response.status,
                "result_type": response.data.resultType,
                "result": result,
            }

        elif tool_name == "prometheus_metadata":
            info = params.get("info")
            if info == "metrics":
                metrics = await client.get_metric_names(params.get("match"))
                return {"status": "success", "metrics": metrics or [], "count": len(metrics or [])}
            elif info == "labels":
                match_list = [params["match"]] if params.get("match") else None
                labels = await client.get_label_names(
                    match_list, params.get("start"), params.get("end")
                )
                return {"status": "success", "labels": labels or [], "count": len(labels or [])}
            elif info == "label_values":
                label = params.get("label")
                if not label:
                    return {"status": "error", "message": "label parameter required"}
                match_list = [params["match"]] if params.get("match") else None
                values = await client.get_label_values(
                    label, match_list, params.get("start"), params.get("end")
                )
                return {
                    "status": "success",
                    "label": label,
                    "values": values or [],
                    "count": len(values or []),
                }

    return {"status": "error", "message": f"Unknown prometheus tool: {tool_name}"}


async def call_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call an lgtm-mcp tool and return the response."""
    if tool_name.startswith("tempo_"):
        return await call_tempo_tool(tool_name, params)
    elif tool_name.startswith("loki_"):
        return await call_loki_tool(tool_name, params)
    elif tool_name.startswith("prometheus_"):
        return await call_prometheus_tool(tool_name, params)
    else:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}


async def run_scenario(scenario: dict) -> ScenarioResult:
    """Run a single test scenario."""
    name = scenario["name"]
    tool = scenario["tool"]
    description = scenario.get("description", "")
    params = scenario.get("params", {})
    max_tokens = scenario["max_tokens"]

    try:
        response = await call_tool(tool, params)
        response_json = json.dumps(response, default=str)
        tokens = count_tokens(response_json)

        return ScenarioResult(
            name=name,
            tool=tool,
            description=description,
            tokens=tokens,
            max_tokens=max_tokens,
            chars=len(response_json),
            passed=tokens <= max_tokens,
            response=response,
        )
    except Exception as e:
        return ScenarioResult(
            name=name,
            tool=tool,
            description=description,
            tokens=0,
            max_tokens=max_tokens,
            chars=0,
            passed=False,
            error=str(e),
        )


def generate_report(results: list[ScenarioResult]) -> str:
    """Generate markdown report."""
    lines = [
        "## Token Efficiency Report",
        "",
        f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    status = "✅" if passed == total else "❌"
    lines.append(f"**Summary:** {status} {passed}/{total} scenarios passed")
    lines.append("")

    for tool_prefix in ["tempo", "loki", "prometheus"]:
        tool_results = [r for r in results if r.tool.startswith(tool_prefix)]
        if not tool_results:
            continue

        lines.append(f"### {tool_prefix.title()} Tools")
        lines.append("")
        lines.append("| Scenario | Tokens | Limit | Chars | Status |")
        lines.append("|----------|--------|-------|-------|--------|")

        for r in tool_results:
            status = "✅" if r.passed else "❌"
            if r.error:
                status = f"⚠️ `{r.error[:30]}...`" if len(r.error) > 30 else f"⚠️ `{r.error}`"
            lines.append(f"| {r.name} | {r.tokens:,} | {r.max_tokens:,} | {r.chars:,} | {status} |")

        lines.append("")

    return "\n".join(lines)


async def main() -> int:
    """Main entry point."""
    # Set config path for lgtm-mcp
    config_path = Path(__file__).parent / "config.yaml"
    os.environ["LGTM_MCP_CONFIG"] = str(config_path)

    # Reset any cached config/managers
    from lgtm_mcp.config import reset_instance_manager

    reset_instance_manager()

    # Load scenarios
    scenarios_file = Path(__file__).parent / "scenarios.yaml"
    scenarios = yaml.safe_load(scenarios_file.read_text())

    print("Running token efficiency evaluation...")
    print("=" * 60)

    results: list[ScenarioResult] = []

    for scenario in scenarios["scenarios"]:
        print(f"  {scenario['name']}...", end=" ", flush=True)
        result = await run_scenario(scenario)
        results.append(result)

        if result.passed:
            print(f"PASS ({result.tokens:,} tokens)")
        elif result.error:
            print(f"ERROR: {result.error[:50]}")
        else:
            print(f"FAIL ({result.tokens:,} > {result.max_tokens:,})")

    print("=" * 60)

    # Generate and save report
    report = generate_report(results)
    report_file = Path(__file__).parent / "report.md"
    report_file.write_text(report)
    print(f"\nReport saved to {report_file}")
    print()
    print(report)

    # Return exit code
    failed = sum(1 for r in results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
