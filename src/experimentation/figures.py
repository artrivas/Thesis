"""Dependency-free SVG figure generation for experiment results."""

from __future__ import annotations

from collections import defaultdict
from html import escape
import math
from pathlib import Path

from experimentation.evaluation import PERTURBATION_GRANULARITY, generate_evaluation_summary, mean
from experimentation.runner import read_result_rows


FIGURE_FILES = {
    "score_vs_alpha": "figure_1_score_vs_alpha.svg",
    "paired_distance_vs_alpha": "figure_2_paired_distance_vs_alpha.svg",
    "mean_shift_vs_paired_shift": "figure_3_mean_shift_vs_paired_shift.svg",
    "granularity_heatmap": "figure_4_granularity_heatmap.svg",
    "runtime_comparison": "figure_5_runtime_comparison.svg",
}

COLORS = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
)


def generate_figures(results_path: Path | str, output_dir: Path | str | None = None) -> dict[str, Path]:
    """Generate all standard SVG figures from a result CSV."""

    rows = [row for row in read_result_rows(results_path) if row.get("status") == "success"]
    figure_dir = Path(output_dir) if output_dir is not None else Path(results_path).parent.parent / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "score_vs_alpha": figure_dir / FIGURE_FILES["score_vs_alpha"],
        "paired_distance_vs_alpha": figure_dir / FIGURE_FILES["paired_distance_vs_alpha"],
        "mean_shift_vs_paired_shift": figure_dir / FIGURE_FILES["mean_shift_vs_paired_shift"],
        "granularity_heatmap": figure_dir / FIGURE_FILES["granularity_heatmap"],
        "runtime_comparison": figure_dir / FIGURE_FILES["runtime_comparison"],
    }
    outputs["score_vs_alpha"].write_text(
        line_panels_svg(rows, "distribution_score", "Figure 1: Score vs alpha", "distribution_score"),
        encoding="utf-8",
    )
    outputs["paired_distance_vs_alpha"].write_text(
        line_panels_svg(rows, "paired_score", "Figure 2: Paired distance vs alpha", "paired_score"),
        encoding="utf-8",
    )
    outputs["mean_shift_vs_paired_shift"].write_text(mean_vs_paired_svg(rows), encoding="utf-8")
    outputs["granularity_heatmap"].write_text(granularity_heatmap_svg(generate_evaluation_summary(rows)), encoding="utf-8")
    outputs["runtime_comparison"].write_text(runtime_bar_svg(rows), encoding="utf-8")
    return outputs


def line_panels_svg(rows: list[dict[str, object]], y_key: str, title: str, y_label: str) -> str:
    if not rows:
        return placeholder_svg(title, "No successful rows available")

    panel_width = 280
    panel_height = 210
    columns = 2
    groups = sorted({(str(row["dataset"]), str(row["perturbation"])) for row in rows})
    panel_rows = math.ceil(len(groups) / columns)
    width = columns * panel_width + 40
    height = panel_rows * panel_height + 90
    body = [
        svg_header(width, height),
        text(20, 30, title, size=18, weight="bold"),
        text(20, 55, f"x: alpha, y: {y_label}", size=11, fill="#555"),
    ]
    color_by_workflow = _workflow_colors(rows)

    for index, (dataset, perturbation) in enumerate(groups):
        x0 = 30 + (index % columns) * panel_width
        y0 = 75 + (index // columns) * panel_height
        body.append(_line_panel(rows, dataset, perturbation, y_key, x0, y0, panel_width - 40, panel_height - 45, color_by_workflow))

    body.append("</svg>")
    return "\n".join(body)


def mean_vs_paired_svg(rows: list[dict[str, object]]) -> str:
    if not rows:
        return placeholder_svg("Figure 3: Mean-shift vs paired-shift", "No successful rows available")

    width = 720
    height = 460
    plot_x = 70
    plot_y = 70
    plot_w = 570
    plot_h = 320
    points = [
        (str(row["workflow"]), _float(row.get("mean_shift_score")), _float(row.get("paired_score")))
        for row in rows
    ]
    points = [(workflow, x, y) for workflow, x, y in points if math.isfinite(x) and math.isfinite(y)]
    max_x = max((point[1] for point in points), default=1.0) or 1.0
    max_y = max((point[2] for point in points), default=1.0) or 1.0
    color_by_workflow = _workflow_colors(rows)

    body = [
        svg_header(width, height),
        text(20, 30, "Figure 3: Mean-shift vs paired-shift", size=18, weight="bold"),
        line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h),
        line(plot_x, plot_y, plot_x, plot_y + plot_h),
        text(plot_x + plot_w / 2 - 40, height - 25, "mean_shift_score", size=12),
        text(15, plot_y + plot_h / 2, "paired_score", size=12),
    ]
    for workflow, x_value, y_value in points:
        x = plot_x + (x_value / max_x) * plot_w
        y = plot_y + plot_h - (y_value / max_y) * plot_h
        body.append(circle(x, y, 3.5, color_by_workflow[workflow], opacity=0.7))
    body.append(_legend(color_by_workflow, plot_x + plot_w + 20, plot_y))
    body.append("</svg>")
    return "\n".join(body)


def granularity_heatmap_svg(summary_rows: list[dict[str, object]]) -> str:
    if not summary_rows:
        return placeholder_svg("Figure 4: Granularity heatmap", "No evaluation rows available")

    workflows = sorted({str(row["workflow"]) for row in summary_rows})
    scales = ("local", "mesoscopic", "global", "multiscale")
    cell_w = 130
    cell_h = 34
    left = 210
    top = 75
    width = left + len(scales) * cell_w + 40
    height = top + len(workflows) * cell_h + 60
    values = _granularity_values(summary_rows, workflows, scales)
    body = [svg_header(width, height), text(20, 30, "Figure 4: Granularity heatmap", size=18, weight="bold")]
    for column, scale in enumerate(scales):
        body.append(text(left + column * cell_w + 8, top - 15, scale, size=11, weight="bold"))
    for row_index, workflow in enumerate(workflows):
        y = top + row_index * cell_h
        body.append(text(20, y + 22, workflow, size=11))
        for column, scale in enumerate(scales):
            x = left + column * cell_w
            value = values[(workflow, scale)]
            body.append(rect(x, y, cell_w - 2, cell_h - 2, _blue_scale(value)))
            body.append(text(x + 44, y + 22, f"{value:.2f}", size=10, fill="#111"))
    body.append("</svg>")
    return "\n".join(body)


def runtime_bar_svg(rows: list[dict[str, object]]) -> str:
    if not rows:
        return placeholder_svg("Figure 5: Runtime comparison", "No successful rows available")

    by_workflow: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_workflow[str(row["workflow"])].append(_float(row.get("runtime_seconds")))
    values = [(workflow, mean([value for value in runtimes if math.isfinite(value)])) for workflow, runtimes in sorted(by_workflow.items())]
    width = 760
    height = 420
    plot_x = 70
    plot_y = 60
    plot_w = 620
    plot_h = 280
    max_value = max((value for _, value in values), default=1.0) or 1.0
    bar_w = plot_w / max(1, len(values)) * 0.7
    gap = plot_w / max(1, len(values))

    body = [
        svg_header(width, height),
        text(20, 30, "Figure 5: Runtime comparison", size=18, weight="bold"),
        line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h),
        line(plot_x, plot_y, plot_x, plot_y + plot_h),
        text(18, plot_y + plot_h / 2, "runtime_seconds", size=12),
    ]
    for index, (workflow, value) in enumerate(values):
        x = plot_x + index * gap + gap * 0.15
        bar_h = (value / max_value) * plot_h
        body.append(rect(x, plot_y + plot_h - bar_h, bar_w, bar_h, COLORS[index % len(COLORS)]))
        body.append(text(x, plot_y + plot_h + 18, workflow[:22], size=10))
    body.append("</svg>")
    return "\n".join(body)


def placeholder_svg(title: str, message: str) -> str:
    return "\n".join(
        [
            svg_header(640, 220),
            text(20, 35, title, size=18, weight="bold"),
            text(20, 80, message, size=13, fill="#555"),
            "</svg>",
        ]
    )


def _line_panel(
    rows: list[dict[str, object]],
    dataset: str,
    perturbation: str,
    y_key: str,
    x0: float,
    y0: float,
    width: float,
    height: float,
    color_by_workflow: dict[str, str],
) -> str:
    selected = [
        row
        for row in rows
        if str(row["dataset"]) == dataset and str(row["perturbation"]) == perturbation
    ]
    grouped: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in selected:
        value = _float(row.get(y_key))
        alpha = _float(row.get("alpha"))
        if math.isfinite(value) and math.isfinite(alpha):
            grouped[str(row["workflow"])][alpha].append(value)

    alphas = sorted({alpha for by_alpha in grouped.values() for alpha in by_alpha})
    y_values = [value for by_alpha in grouped.values() for values in by_alpha.values() for value in values]
    x_min = min(alphas, default=0.0)
    x_max = max(alphas, default=1.0)
    y_max = max(y_values, default=1.0) or 1.0
    if x_min == x_max:
        x_max = x_min + 1.0

    elements = [
        text(x0, y0 - 18, f"{dataset} / {perturbation}", size=11, weight="bold"),
        line(x0, y0 + height, x0 + width, y0 + height),
        line(x0, y0, x0, y0 + height),
    ]
    for workflow, by_alpha in sorted(grouped.items()):
        points = []
        for alpha in sorted(by_alpha):
            x = x0 + ((alpha - x_min) / (x_max - x_min)) * width
            y = y0 + height - (mean(by_alpha[alpha]) / y_max) * height
            points.append((x, y))
        if len(points) == 1:
            elements.append(circle(points[0][0], points[0][1], 3, color_by_workflow[workflow]))
        elif points:
            elements.append(polyline(points, color_by_workflow[workflow]))
            elements.append(text(points[-1][0] + 4, points[-1][1], workflow[:16], size=8, fill=color_by_workflow[workflow]))
    return "\n".join(elements)


def _workflow_colors(rows: list[dict[str, object]]) -> dict[str, str]:
    workflows = sorted({str(row["workflow"]) for row in rows})
    return {workflow: COLORS[index % len(COLORS)] for index, workflow in enumerate(workflows)}


def _granularity_values(
    summary_rows: list[dict[str, object]],
    workflows: list[str],
    scales: tuple[str, ...],
) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in summary_rows:
        workflow = str(row["workflow"])
        score = max(0.0, min(1.0, _float(row.get("sensitivity"))))
        label = str(row.get("granularity_label") or PERTURBATION_GRANULARITY.get(str(row.get("perturbation")), "unknown"))
        for scale in label.split("/"):
            values[(workflow, scale)].append(score)
        values[(workflow, "multiscale")].append(score)
    return {
        (workflow, scale): mean(values.get((workflow, scale), [0.0]))
        for workflow in workflows
        for scale in scales
    }


def _blue_scale(value: float) -> str:
    value = max(0.0, min(1.0, value))
    channel = int(245 - value * 150)
    return f"rgb({channel},{channel},{255})"


def svg_header(width: float, height: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">'
        '<rect width="100%" height="100%" fill="white"/>'
    )


def text(x: float, y: float, value: str, size: int = 12, fill: str = "#222", weight: str = "normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'
    )


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = "#333") -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="1"/>'


def polyline(points: list[tuple[float, float]], stroke: str) -> str:
    value = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{value}" fill="none" stroke="{stroke}" stroke-width="1.8"/>'


def circle(x: float, y: float, radius: float, fill: str, opacity: float = 1.0) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}" opacity="{opacity:.2f}"/>'


def rect(x: float, y: float, width: float, height: float, fill: str) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{fill}" stroke="#fff"/>'


def _legend(color_by_workflow: dict[str, str], x: float, y: float) -> str:
    items = []
    for index, (workflow, color) in enumerate(sorted(color_by_workflow.items())):
        item_y = y + index * 20
        items.append(circle(x, item_y - 4, 4, color))
        items.append(text(x + 10, item_y, workflow, size=10))
    return "\n".join(items)


def _float(value: object) -> float:
    if value in (None, ""):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan
