"""ASCII chart utilities for metrics visualization."""

import re
from datetime import datetime

import asciichartpy


ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE_PATTERN.sub("", text)


def format_time_label(timestamp: float, duration_seconds: float) -> str:
    """Format timestamp based on time range duration.

    Args:
        timestamp: Unix timestamp
        duration_seconds: Total duration of the time range

    Returns:
        Formatted time string
    """
    dt = datetime.fromtimestamp(timestamp)
    if duration_seconds <= 3600:  # <= 1 hour
        return dt.strftime("%H:%M:%S")
    elif duration_seconds <= 86400:  # <= 1 day
        return dt.strftime("%H:%M")
    else:
        return dt.strftime("%m-%d %H:%M")


def add_time_axis(
    chart: str,
    timestamps: list[float],
    num_ticks: int = 10,
) -> str:
    """Add time axis labels below an ASCII chart.

    Args:
        chart: The ASCII chart string from asciichartpy
        timestamps: List of timestamps corresponding to each data point
        num_ticks: Number of tick marks on the axis

    Returns:
        Chart with time axis appended
    """
    lines = chart.split("\n")
    if not lines or not timestamps:
        return chart

    max_line_len = max(len(strip_ansi(line)) for line in lines)

    y_axis_width = 0
    for line in lines:
        stripped = strip_ansi(line)
        for i, char in enumerate(stripped):
            if char in "┼┤":
                y_axis_width = i + 1
                break
        if y_axis_width > 0:
            break

    if y_axis_width == 0:
        y_axis_width = 10

    chart_width = max_line_len - y_axis_width
    if chart_width <= 0:
        return chart

    num_data_points = len(timestamps)
    duration = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0

    axis_line = " " * y_axis_width
    tick_positions = [int(chart_width * i / (num_ticks - 1)) for i in range(num_ticks)]

    axis_chars = list("─" * chart_width)
    for i, pos in enumerate(tick_positions):
        if pos < len(axis_chars):
            if i == 0:
                axis_chars[pos] = "├"
            elif i == num_ticks - 1:
                axis_chars[min(pos, len(axis_chars) - 1)] = "┤"
            else:
                axis_chars[pos] = "┼"

    axis_line += "".join(axis_chars)

    label_tick_indices = [1, (num_ticks - 1) // 2, num_ticks - 2]
    label_positions = [tick_positions[i] for i in label_tick_indices]

    data_indices = [int((num_data_points - 1) * i / (num_ticks - 1)) for i in label_tick_indices]
    label_timestamps = [timestamps[i] for i in data_indices]
    labels = [format_time_label(ts, duration) for ts in label_timestamps]

    label_line = " " * y_axis_width
    label_chars = [" "] * chart_width

    for i, (pos, label) in enumerate(zip(label_positions, labels)):
        start_pos = pos - len(label) // 2

        for j, char in enumerate(label):
            if 0 <= start_pos + j < len(label_chars):
                label_chars[start_pos + j] = char

    label_line += "".join(label_chars)

    return chart + "\n" + axis_line + "\n" + label_line


SERIES_COLORS = [
    (asciichartpy.lightblue, "lightblue"),
    (asciichartpy.lightgreen, "lightgreen"),
    (asciichartpy.lightyellow, "lightyellow"),
    (asciichartpy.lightmagenta, "lightmagenta"),
    (asciichartpy.lightcyan, "lightcyan"),
]


def get_series_colors(count: int) -> list:
    """Get color codes for the specified number of series."""
    return [SERIES_COLORS[i % len(SERIES_COLORS)][0] for i in range(count)]


def format_legend(legend_items: list[dict], max_label_length: int = 50) -> str:
    """Format legend items for display below the chart.

    Args:
        legend_items: List of legend items with series, metric, and label
        max_label_length: Maximum length for each label

    Returns:
        Formatted legend string
    """
    if not legend_items:
        return ""

    lines = ["", "Legend:"]
    for item in legend_items:
        idx = item["series"] - 1
        color_code, color_name = SERIES_COLORS[idx % len(SERIES_COLORS)]
        label = item.get("label", "")

        if len(label) > max_label_length:
            label = label[: max_label_length - 3] + "..."

        colored_marker = f"{color_code}━━{asciichartpy.reset}"
        lines.append(f"  [{colored_marker}] ({color_name}) {label}")

    return "\n".join(lines)


def format_metric_label(metric: dict[str, str], max_length: int = 60) -> str:
    """Format metric labels for display in legend.

    Args:
        metric: Dictionary of metric labels
        max_length: Maximum length of the formatted string

    Returns:
        Formatted label string
    """
    parts = []
    for key, value in metric.items():
        if key != "__name__":
            parts.append(f'{key}="{value}"')

    result = ", ".join(parts)
    if len(result) > max_length:
        result = result[: max_length - 3] + "..."
    return result


def plot_time_series(
    series_data: list[dict],
    height: int = 15,
    max_series: int = 5,
) -> dict:
    """Plot time series data as ASCII chart.

    Args:
        series_data: List of series, each with:
            - metric: dict of labels
            - values: list of {"timestamp": float, "value": str} dicts
        height: Chart height in lines
        max_series: Maximum number of series to plot

    Returns:
        Dictionary with chart, legend, and metadata
    """
    if not series_data:
        return {
            "chart": "(no data)",
            "legend": [],
            "metadata": {
                "series_count": 0,
                "data_points": 0,
                "time_range": None,
                "value_range": None,
            },
            "truncated": False,
        }

    truncated = len(series_data) > max_series
    series_to_plot = series_data[:max_series]

    all_values: list[list[float]] = []
    all_timestamps: list[float] = []
    legend = []

    for idx, series in enumerate(series_to_plot):
        metric = series.get("metric", {})
        values_list = series.get("values", [])

        if not values_list:
            continue

        float_values = []
        for v in values_list:
            try:
                float_values.append(float(v["value"]))
            except (ValueError, TypeError):
                float_values.append(float("nan"))

        all_values.append(float_values)

        if not all_timestamps:
            all_timestamps = [float(v["timestamp"]) for v in values_list]

        legend.append(
            {
                "series": idx + 1,
                "metric": metric,
                "label": format_metric_label(metric),
            }
        )

    if not all_values:
        return {
            "chart": "(no numeric data)",
            "legend": [],
            "metadata": {
                "series_count": len(series_data),
                "data_points": 0,
                "time_range": None,
                "value_range": None,
            },
            "truncated": truncated,
        }

    flat_values = [v for series in all_values for v in series if not (v != v)]  # filter NaN
    min_val = min(flat_values) if flat_values else 0
    max_val = max(flat_values) if flat_values else 0

    start_ts = min(all_timestamps) if all_timestamps else 0
    end_ts = max(all_timestamps) if all_timestamps else 0

    if len(all_values) == 1:
        chart_data = all_values[0]
    else:
        chart_data = all_values

    try:
        config = {"height": height}
        if len(all_values) > 1:
            config["colors"] = get_series_colors(len(all_values))
        chart = asciichartpy.plot(chart_data, config)
    except Exception as e:
        return {
            "chart": f"(chart error: {e})",
            "legend": legend,
            "metadata": {
                "series_count": len(series_data),
                "data_points": len(all_timestamps),
                "time_range": {"start": start_ts, "end": end_ts},
                "value_range": {"min": min_val, "max": max_val},
            },
            "truncated": truncated,
        }

    if all_timestamps:
        chart = add_time_axis(chart, all_timestamps)

    if len(all_values) > 1:
        chart += format_legend(legend)

    return {
        "chart": chart,
        "legend": legend,
        "metadata": {
            "series_count": len(series_data),
            "data_points": len(all_timestamps),
            "time_range": {
                "start": datetime.fromtimestamp(start_ts).isoformat() if start_ts else None,
                "end": datetime.fromtimestamp(end_ts).isoformat() if end_ts else None,
            },
            "value_range": {"min": min_val, "max": max_val},
        },
        "truncated": truncated,
    }
