"""ASCII chart utilities for metrics visualization."""

from datetime import datetime

import asciichartpy


def format_time_label(timestamp: float, duration_seconds: float) -> str:
    """Format timestamp based on time range duration."""
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
    y_axis_width: int,
    num_ticks: int = 10,
) -> str:
    """Add time axis labels below an ASCII chart."""
    lines = chart.split("\n")
    if not lines or not timestamps:
        return chart

    max_line_len = max(len(line) for line in lines)
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

    # Show labels at start, middle, and end positions
    label_data_indices = [0, num_data_points // 2, num_data_points - 1]
    label_positions = [0, chart_width // 2, chart_width - 1]
    label_timestamps = [timestamps[i] for i in label_data_indices]
    labels = [format_time_label(ts, duration) for ts in label_timestamps]

    label_line = " " * y_axis_width
    label_chars = [" "] * chart_width

    for idx, (pos, label) in enumerate(zip(label_positions, labels)):
        if idx == 0:  # Left-align first label
            start_pos = pos
        elif idx == len(labels) - 1:  # Right-align last label
            start_pos = pos - len(label) + 1
        else:  # Center middle label
            start_pos = pos - len(label) // 2

        for j, char in enumerate(label):
            if 0 <= start_pos + j < len(label_chars):
                label_chars[start_pos + j] = char

    label_line += "".join(label_chars)

    return chart + "\n" + axis_line + "\n" + label_line


def format_metric_label(metric: dict[str, str], max_length: int = 80) -> str:
    """Format metric labels for display as chart title."""
    parts = []
    for key, value in metric.items():
        if key != "__name__":
            parts.append(f'{key}="{value}"')

    result = ", ".join(parts)
    if len(result) > max_length:
        result = result[: max_length - 3] + "..."
    return result


def calculate_y_axis_width(min_val: float, max_val: float) -> int:
    """Calculate the width needed for Y-axis labels."""
    test_values = [min_val, max_val, (min_val + max_val) / 2]
    max_width = 0
    for val in test_values:
        if abs(val) >= 1000000:
            formatted = f"{val:.2e}"
        elif abs(val) >= 1:
            formatted = f"{val:.2f}"
        else:
            formatted = f"{val:.4f}"
        max_width = max(max_width, len(formatted))
    return max_width + 3  # +3 for padding and axis char


def plot_single_series(
    values: list[float],
    timestamps: list[float],
    height: int,
    min_val: float,
    max_val: float,
    y_axis_width: int,
) -> str:
    """Plot a single series with fixed axis dimensions."""
    format_str = "{:" + str(y_axis_width - 1) + ".2f} "
    config = {
        "height": height,
        "min": min_val,
        "max": max_val,
        "format": format_str,
    }
    chart = asciichartpy.plot(values, config)
    chart = add_time_axis(chart, timestamps, y_axis_width)
    return chart


def plot_time_series(
    series_data: list[dict],
    height: int = 12,
    max_series: int = 5,
) -> dict:
    """Plot time series data as separate ASCII charts with shared axis dimensions.

    Args:
        series_data: List of series, each with:
            - metric: dict of labels
            - values: list of {"timestamp": float, "value": str} dicts
        height: Chart height in lines for each chart
        max_series: Maximum number of series to plot (default: 5)

    Returns:
        Dictionary with charts list and metadata
    """
    if not series_data:
        return {
            "charts": [],
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

    all_series_values: list[list[float]] = []
    all_series_metrics: list[dict] = []
    all_timestamps: list[float] = []

    for series in series_to_plot:
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

        all_series_values.append(float_values)
        all_series_metrics.append(metric)

        if not all_timestamps:
            all_timestamps = [float(v["timestamp"]) for v in values_list]

    if not all_series_values:
        return {
            "charts": [],
            "metadata": {
                "series_count": len(series_data),
                "data_points": 0,
                "time_range": None,
                "value_range": None,
            },
            "truncated": truncated,
        }

    # Calculate global min/max across all series for consistent Y-axis
    flat_values = [v for series in all_series_values for v in series if not (v != v)]
    global_min = min(flat_values) if flat_values else 0
    global_max = max(flat_values) if flat_values else 0

    # Add small padding to min/max
    value_range = global_max - global_min
    if value_range > 0:
        padding = value_range * 0.05
        global_min -= padding
        global_max += padding

    y_axis_width = calculate_y_axis_width(global_min, global_max)

    start_ts = min(all_timestamps) if all_timestamps else 0
    end_ts = max(all_timestamps) if all_timestamps else 0

    charts = []
    for idx, (values, metric) in enumerate(zip(all_series_values, all_series_metrics)):
        label = format_metric_label(metric)
        try:
            chart = plot_single_series(
                values, all_timestamps, height, global_min, global_max, y_axis_width
            )
            charts.append(
                {
                    "series": idx + 1,
                    "label": label,
                    "chart": f"[{idx + 1}/{len(all_series_values)}] {label}\n{chart}",
                }
            )
        except Exception as e:
            charts.append(
                {
                    "series": idx + 1,
                    "label": label,
                    "chart": f"[{idx + 1}/{len(all_series_values)}] {label}\n(chart error: {e})",
                }
            )

    return {
        "charts": charts,
        "metadata": {
            "series_count": len(series_data),
            "series_plotted": len(charts),
            "data_points": len(all_timestamps),
            "time_range": {
                "start": datetime.fromtimestamp(start_ts).isoformat() if start_ts else None,
                "end": datetime.fromtimestamp(end_ts).isoformat() if end_ts else None,
            },
            "value_range": {"min": global_min, "max": global_max},
        },
        "truncated": truncated,
    }
