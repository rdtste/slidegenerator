"""Chart generation service — creates professional charts using template colors.

Generates chart images (PNG) using matplotlib, styled to match
the template's color DNA. Supports: bar, line, pie, donut, stacked_bar.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-load matplotlib to avoid import cost on startup
_MPL_AVAILABLE: bool | None = None


def _ensure_matplotlib() -> bool:
    global _MPL_AVAILABLE
    if _MPL_AVAILABLE is None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            _MPL_AVAILABLE = True
        except ImportError:
            logger.warning("matplotlib not installed — chart generation disabled")
            _MPL_AVAILABLE = False
    return _MPL_AVAILABLE


# Chart data pattern: ```chart\n{json}\n```
_CHART_BLOCK_RE = re.compile(
    r"```chart\s*\n(.*?)\n```",
    re.DOTALL,
)


def parse_chart_data(text: str) -> dict | None:
    """Extract chart data JSON from a ```chart ... ``` code block."""
    match = _CHART_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse chart JSON from slide body")
        return None


def generate_chart(
    chart_data: dict,
    colors: list[str] | None = None,
    font_family: str = "Calibri",
    width_px: int = 1200,
    height_px: int = 800,
    bg_color: str = "transparent",
    text_color: str = "#333333",
    grid_color: str = "#E0E0E0",
) -> Path | None:
    """Generate a chart image from structured data.

    chart_data format:
    {
        "type": "bar" | "line" | "pie" | "donut" | "stacked_bar" | "horizontal_bar",
        "title": "Chart Title",
        "labels": ["A", "B", "C"],
        "datasets": [
            {"label": "Series 1", "values": [10, 20, 30]},
            {"label": "Series 2", "values": [15, 25, 35]}
        ],
        "x_label": "Category",
        "y_label": "Value",
        "show_values": true,
        "show_legend": true
    }
    """
    if not _ensure_matplotlib():
        return None

    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import numpy as np

    chart_type = chart_data.get("type", "bar")
    title = chart_data.get("title", "")
    labels = chart_data.get("labels", [])
    datasets = chart_data.get("datasets", [])
    x_label = chart_data.get("x_label", "")
    y_label = chart_data.get("y_label", "")
    show_values = chart_data.get("show_values", True)
    show_legend = chart_data.get("show_legend", len(datasets) > 1)

    if not labels or not datasets:
        logger.warning("Chart data missing labels or datasets")
        return None

    # Default corporate colors if none provided
    if not colors:
        colors = ["#0969da", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]

    # DPI for high-quality output
    dpi = 200
    fig_w = width_px / dpi
    fig_h = height_px / dpi

    # Style setup — larger fonts for readability in presentations
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [font_family, "DejaVu Sans", "Arial", "Helvetica"],
        "font.size": 14,
        "axes.labelcolor": text_color,
        "text.color": text_color,
        "xtick.color": text_color,
        "ytick.color": text_color,
    })

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    if bg_color == "transparent":
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
    else:
        fig.patch.set_facecolor(bg_color)
        ax.patch.set_facecolor(bg_color)

    try:
        if chart_type in ("pie", "donut"):
            _draw_pie(ax, labels, datasets, colors, chart_type == "donut", show_values)
        elif chart_type == "line":
            _draw_line(ax, labels, datasets, colors, show_values, grid_color)
        elif chart_type == "horizontal_bar":
            _draw_horizontal_bar(ax, labels, datasets, colors, show_values, grid_color)
        elif chart_type == "stacked_bar":
            _draw_stacked_bar(ax, labels, datasets, colors, show_values, grid_color)
        else:
            _draw_bar(ax, labels, datasets, colors, show_values, grid_color)

        if title:
            ax.set_title(title, fontsize=18, fontweight="bold", color=text_color, pad=20)

        if chart_type not in ("pie", "donut"):
            if x_label:
                ax.set_xlabel(x_label, fontsize=14)
            if y_label:
                ax.set_ylabel(y_label, fontsize=14)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color(grid_color)
            ax.spines["bottom"].set_color(grid_color)

        if show_legend and len(datasets) > 1 and chart_type not in ("pie", "donut"):
            ax.legend(frameon=False, fontsize=13)

        fig.tight_layout(pad=1.5)

        output = Path(tempfile.mktemp(suffix=".png", prefix="chart_"))
        fig.savefig(
            str(output),
            dpi=dpi,
            bbox_inches="tight",
            transparent=(bg_color == "transparent"),
            pad_inches=0.3,
        )
        logger.info(f"Chart generated: {chart_type}, {len(labels)} labels -> {output}")
        return output

    except Exception:
        logger.exception("Failed to generate chart")
        return None
    finally:
        plt.close(fig)


def _draw_bar(ax, labels, datasets, colors, show_values, grid_color) -> None:
    import numpy as np

    x = np.arange(len(labels))
    n = len(datasets)
    width = 0.7 / max(n, 1)

    for i, ds in enumerate(datasets):
        values = ds.get("values", [])
        offset = (i - n / 2 + 0.5) * width
        bars = ax.bar(x + offset, values, width * 0.9, label=ds.get("label", ""),
                       color=colors[i % len(colors)], zorder=3)
        if show_values:
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, h,
                        _format_value(h), ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=13)
    ax.yaxis.grid(True, color=grid_color, linewidth=0.5, zorder=0)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_axisbelow(True)


def _draw_horizontal_bar(ax, labels, datasets, colors, show_values, grid_color) -> None:
    import numpy as np

    y = np.arange(len(labels))
    values = datasets[0].get("values", []) if datasets else []
    bar_colors = [colors[i % len(colors)] for i in range(len(values))]

    bars = ax.barh(y, values, 0.6, color=bar_colors, zorder=3)
    if show_values:
        for bar in bars:
            w = bar.get_width()
            ax.text(w, bar.get_y() + bar.get_height() / 2,
                    f" {_format_value(w)}", ha="left", va="center", fontsize=12, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=13)
    ax.xaxis.grid(True, color=grid_color, linewidth=0.5, zorder=0)
    ax.tick_params(axis="x", labelsize=12)
    ax.set_axisbelow(True)
    ax.invert_yaxis()


def _draw_stacked_bar(ax, labels, datasets, colors, show_values, grid_color) -> None:
    import numpy as np

    x = np.arange(len(labels))
    bottoms = np.zeros(len(labels))

    for i, ds in enumerate(datasets):
        values = np.array(ds.get("values", [0] * len(labels)), dtype=float)
        ax.bar(x, values, 0.6, bottom=bottoms, label=ds.get("label", ""),
               color=colors[i % len(colors)], zorder=3)
        if show_values:
            for j, (v, b) in enumerate(zip(values, bottoms)):
                if v > 0:
                    ax.text(j, b + v / 2, _format_value(v),
                            ha="center", va="center", fontsize=11, color="white", fontweight="bold")
        bottoms += values

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=13)
    ax.yaxis.grid(True, color=grid_color, linewidth=0.5, zorder=0)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_axisbelow(True)


def _draw_line(ax, labels, datasets, colors, show_values, grid_color) -> None:
    import numpy as np

    x = np.arange(len(labels))

    for i, ds in enumerate(datasets):
        values = ds.get("values", [])
        color = colors[i % len(colors)]
        ax.plot(x, values, marker="o", markersize=6, linewidth=2.5,
                label=ds.get("label", ""), color=color, zorder=3)
        if show_values:
            for j, v in enumerate(values):
                ax.text(j, v, f" {_format_value(v)}", fontsize=11, fontweight="bold", va="bottom")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=13)
    ax.yaxis.grid(True, color=grid_color, linewidth=0.5, zorder=0)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_axisbelow(True)


def _draw_pie(ax, labels, datasets, colors, donut, show_values) -> None:
    values = datasets[0].get("values", []) if datasets else []
    pie_colors = [colors[i % len(colors)] for i in range(len(values))]

    def autopct(pct):
        return f"{pct:.0f}%" if pct >= 5 else ""

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels if not donut else None,
        colors=pie_colors,
        autopct=autopct if show_values else None,
        startangle=90,
        pctdistance=0.75 if donut else 0.6,
        textprops={"fontsize": 13},
    )

    for at in autotexts:
        at.set_fontsize(13)
        at.set_fontweight("bold")
        at.set_color("white")

    if donut:
        centre = plt.Circle((0, 0), 0.55, fc="white")
        ax.add_artist(centre)
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5),
                  frameon=False, fontsize=13)

    ax.set_aspect("equal")


def _format_value(v: float) -> str:
    """Format numeric value for chart labels."""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"
