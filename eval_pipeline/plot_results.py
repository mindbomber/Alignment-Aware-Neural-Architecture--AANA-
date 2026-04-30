import argparse
import csv
import pathlib
import statistics


PREFERRED_CORRECTION_ORDER = [
    "baseline",
    "weak",
    "strong",
    "aana_loop",
    "aana_tools_v1",
    "aana_tools_structured",
    "aana_tools_detect_only",
    "aana_tools_generic_repair",
    "aana_tools_schema",
    "aana_tools_hybrid",
    "aana_tools_hybrid_gate",
    "structured_direct",
    "schema_direct",
    "hybrid_direct",
    "hybrid_gate_direct",
]


CORRECTION_LABELS = {
    "baseline": "Baseline",
    "weak": "Weak",
    "strong": "Strong",
    "aana_loop": "AANA Loop",
    "aana_tools_v1": "AANA Tools",
    "aana_tools_structured": "AANA Structured",
    "aana_tools_detect_only": "Detect Only",
    "aana_tools_generic_repair": "Generic Repair",
    "aana_tools_schema": "Schema Loop",
    "aana_tools_hybrid": "Hybrid Loop",
    "aana_tools_hybrid_gate": "Hybrid Gate",
    "structured_direct": "Structured Direct",
    "schema_direct": "Schema Direct",
    "hybrid_direct": "Hybrid Direct",
    "hybrid_gate_direct": "Gate Direct",
}


def read_csv(path):
    with pathlib.Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fmean(rows, field):
    vals = [float(r[field]) for r in rows]
    return statistics.fmean(vals) if vals else 0.0


def weighted_mean(rows, field):
    total = sum(int(row.get("n", 1) or 1) for row in rows)
    if not total:
        return 0.0
    return sum(float(row[field]) * int(row.get("n", 1) or 1) for row in rows) / total


def group_mean(rows, group_fields, value_fields):
    groups = {}
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        groups.setdefault(key, []).append(row)
    out = []
    for key, members in sorted(groups.items()):
        item = dict(zip(group_fields, key))
        for field in value_fields:
            item[field] = fmean(members, field)
        out.append(item)
    return out


def group_weighted_mean(rows, group_fields, value_fields):
    groups = {}
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        groups.setdefault(key, []).append(row)
    out = []
    for key, members in sorted(groups.items()):
        item = dict(zip(group_fields, key))
        for field in value_fields:
            item[field] = weighted_mean(members, field)
        out.append(item)
    return out


def ordered_values(rows, field, preferred=None):
    present = {row[field] for row in rows}
    preferred = preferred or []
    ordered = [item for item in preferred if item in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def label_correction(correction):
    return CORRECTION_LABELS.get(correction, correction.replace("_", " ").title())


def try_matplotlib_plots(rows, output_dir):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    by_model = group_mean(rows, ["model"], ["capability_score", "alignment_score"])
    plt.figure()
    plt.plot([r["model"] for r in by_model], [r["capability_score"] for r in by_model], marker="o", label="Capability")
    plt.plot([r["model"] for r in by_model], [r["alignment_score"] for r in by_model], marker="o", label="Alignment")
    plt.title("Capability vs Alignment by Model")
    plt.ylabel("Score")
    plt.xticks(rotation=20, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "fig1_cap_vs_align.png")

    plt.figure()
    for pressure in ["low", "high"]:
        subset = [r for r in rows if r["pressure"] == pressure]
        grouped = group_mean(subset, ["model"], ["gap_score"])
        plt.plot([r["model"] for r in grouped], [r["gap_score"] for r in grouped], marker="o", label=f"{pressure} pressure")
    plt.title("Gap vs Pressure")
    plt.ylabel("Gap Score")
    plt.xticks(rotation=20, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "fig2_gap_pressure.png")

    plt.figure()
    for correction in ordered_values(rows, "correction", PREFERRED_CORRECTION_ORDER):
        subset = [r for r in rows if r["correction"] == correction]
        grouped = group_mean(subset, ["model"], ["gap_score"])
        plt.plot([r["model"] for r in grouped], [r["gap_score"] for r in grouped], marker="o", label=label_correction(correction))
    plt.title("Gap vs Correction")
    plt.ylabel("Gap Score")
    plt.xticks(rotation=20, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "fig3_gap_correction.png")
    return True


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_line_plot(path, title, series):
    width, height = 760, 420
    margin = 64
    labels = sorted({label for _, points in series for label, _ in points})
    if not labels:
        labels = ["no data"]
    values = [value for _, points in series for _, value in points] or [0]
    ymin = min(0, min(values))
    ymax = max(1, max(values))
    if ymax == ymin:
        ymax = ymin + 1

    def x_pos(label):
        if len(labels) == 1:
            return width / 2
        return margin + labels.index(label) * (width - 2 * margin) / (len(labels) - 1)

    def y_pos(value):
        return height - margin - (value - ymin) * (height - 2 * margin) / (ymax - ymin)

    colors = ["#2563eb", "#dc2626", "#059669", "#9333ea", "#ea580c"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Arial" font-size="20">{esc(title)}</text>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#333"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#333"/>',
    ]
    for label in labels:
        x = x_pos(label)
        parts.append(f'<text x="{x}" y="{height-28}" text-anchor="middle" font-family="Arial" font-size="12">{esc(label)}</text>')
    for i, (name, points) in enumerate(series):
        color = colors[i % len(colors)]
        coords = " ".join(f"{x_pos(label)},{y_pos(value)}" for label, value in points)
        if coords:
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')
        for label, value in points:
            x, y = x_pos(label), y_pos(value)
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{width-margin-130}" y="{margin + i*20}" font-family="Arial" font-size="13" fill="{color}">{esc(name)}</text>')
    parts.append("</svg>")
    pathlib.Path(path).write_text("\n".join(parts), encoding="utf-8")


def color_scale(value, low=-0.15, high=0.35, higher_is_bad=True):
    if high == low:
        high = low + 1
    t = max(0, min(1, (value - low) / (high - low)))
    if not higher_is_bad:
        t = 1 - t
    # green -> amber -> red, because larger positive gaps indicate divergence.
    if t < 0.5:
        u = t / 0.5
        r, g, b = int(35 + 210 * u), int(150 + 40 * u), int(95 - 35 * u)
    else:
        u = (t - 0.5) / 0.5
        r, g, b = int(245 - 25 * u), int(190 - 115 * u), int(60)
    return f"rgb({r},{g},{b})"


def svg_bar_chart(path, title, data, y_label, value_min=None, value_max=None):
    width, height = 980, 500
    left, right, top, bottom = 86, 38, 64, 110
    plot_w = width - left - right
    plot_h = height - top - bottom
    values = [value for _, value in data] or [0]
    ymin = min(0, min(values)) if value_min is None else value_min
    ymax = max(1, max(values)) if value_max is None else value_max
    if ymin == ymax:
        ymax = ymin + 1
    zero_y = top + plot_h - (0 - ymin) * plot_h / (ymax - ymin)
    group_w = plot_w / max(1, len(data))
    bar_w = min(62, group_w * 0.58)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111827}.small{font-size:12px}.title{font-size:20px;font-weight:700}.axis{stroke:#374151}.grid{stroke:#e5e7eb}</style>',
        f'<text class="title" x="{width/2}" y="32" text-anchor="middle">{esc(title)}</text>',
        f'<text class="small" x="20" y="{top + plot_h/2}" transform="rotate(-90 20 {top + plot_h/2})" text-anchor="middle">{esc(y_label)}</text>',
    ]
    for i in range(6):
        value = ymin + (ymax - ymin) * i / 5
        y = top + plot_h - (value - ymin) * plot_h / (ymax - ymin)
        parts.append(f'<line class="grid" x1="{left}" y1="{y}" x2="{width-right}" y2="{y}"/>')
        parts.append(f'<text class="small" x="{left-10}" y="{y+4}" text-anchor="end">{value:.2f}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="{zero_y}" x2="{width-right}" y2="{zero_y}"/>')

    for idx, (label, value) in enumerate(data):
        x = left + idx * group_w + (group_w - bar_w) / 2
        y_value = top + plot_h - (value - ymin) * plot_h / (ymax - ymin)
        y = min(y_value, zero_y)
        h = max(1, abs(zero_y - y_value))
        color = "#2563eb" if value >= 0 else "#059669"
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="3"/>')
        text_y = y - 8 if value >= 0 else y + h + 18
        parts.append(f'<text class="small" x="{x+bar_w/2}" y="{text_y}" text-anchor="middle">{value:.3f}</text>')
        parts.append(f'<text class="small" x="{x+bar_w/2}" y="{height-52}" text-anchor="middle">{esc(label)}</text>')
    parts.append("</svg>")
    pathlib.Path(path).write_text("\n".join(parts), encoding="utf-8")


def svg_heatmap(path, title, rows, x_field, y_field, value_field, higher_is_bad=True):
    x_values = ordered_values(rows, x_field, PREFERRED_CORRECTION_ORDER if x_field == "correction" else None)
    y_values = ordered_values(rows, y_field)
    matrix = {(row[y_field], row[x_field]): float(row[value_field]) for row in rows}
    cell_w, cell_h = 128, 58
    left, top = 210, 78
    width = max(760, left + len(x_values) * cell_w + 50)
    height = max(320, top + len(y_values) * cell_h + 55)
    values = list(matrix.values()) or [0]
    low, high = min(values), max(values)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111827}.small{font-size:12px}.label{font-size:13px}.title{font-size:20px;font-weight:700}</style>',
        f'<text class="title" x="{width/2}" y="32" text-anchor="middle">{esc(title)}</text>',
    ]
    for j, x_value in enumerate(x_values):
        label = label_correction(x_value) if x_field == "correction" else x_value
        x = left + j * cell_w + cell_w / 2
        parts.append(f'<text class="small" x="{x}" y="{top-18}" text-anchor="middle">{esc(label)}</text>')
    for i, y_value in enumerate(y_values):
        y = top + i * cell_h
        parts.append(f'<text class="label" x="{left-12}" y="{y+cell_h/2+5}" text-anchor="end">{esc(y_value)}</text>')
        for j, x_value in enumerate(x_values):
            value = matrix.get((y_value, x_value), 0.0)
            x = left + j * cell_w
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h-4}" fill="{color_scale(value, low, high, higher_is_bad)}" rx="3"/>')
            parts.append(f'<text class="label" x="{x+(cell_w-4)/2}" y="{y+cell_h/2+5}" text-anchor="middle">{value:.3f}</text>')
    parts.append("</svg>")
    pathlib.Path(path).write_text("\n".join(parts), encoding="utf-8")


def svg_fallback_plots(rows, output_dir):
    by_model = group_mean(rows, ["model"], ["capability_score", "alignment_score"])
    svg_line_plot(
        output_dir / "fig1_cap_vs_align.svg",
        "Capability vs Alignment by Model",
        [
            ("Capability", [(r["model"], r["capability_score"]) for r in by_model]),
            ("Alignment", [(r["model"], r["alignment_score"]) for r in by_model]),
        ],
    )

    pressure_series = []
    for pressure in ["low", "high"]:
        subset = [r for r in rows if r["pressure"] == pressure]
        grouped = group_mean(subset, ["model"], ["gap_score"])
        pressure_series.append((f"{pressure} pressure", [(r["model"], r["gap_score"]) for r in grouped]))
    svg_line_plot(output_dir / "fig2_gap_pressure.svg", "Gap vs Pressure", pressure_series)

    correction_series = []
    for correction in ordered_values(rows, "correction", PREFERRED_CORRECTION_ORDER):
        subset = [r for r in rows if r["correction"] == correction]
        grouped = group_mean(subset, ["model"], ["gap_score"])
        correction_series.append((label_correction(correction), [(r["model"], r["gap_score"]) for r in grouped]))
    svg_line_plot(output_dir / "fig3_gap_correction.svg", "Gap vs Correction", correction_series)


def svg_report_plots(rows, output_dir):
    by_pressure = group_weighted_mean(rows, ["pressure"], ["gap_score", "capability_score", "alignment_score"])
    svg_bar_chart(
        output_dir / "paper_gap_by_pressure.svg",
        "Capability-Alignment Gap by Pressure",
        [(row["pressure"], row["gap_score"]) for row in by_pressure],
        "gap score",
        value_min=min(-0.1, min((row["gap_score"] for row in by_pressure), default=0)),
        value_max=max(0.2, max((row["gap_score"] for row in by_pressure), default=0)),
    )

    by_correction = group_weighted_mean(rows, ["correction"], ["gap_score", "capability_score", "alignment_score"])
    correction_order = ordered_values(rows, "correction", PREFERRED_CORRECTION_ORDER)
    by_correction = sorted(by_correction, key=lambda row: correction_order.index(row["correction"]))
    svg_bar_chart(
        output_dir / "paper_gap_by_correction.svg",
        "Capability-Alignment Gap by Correction Condition",
        [(label_correction(row["correction"]), row["gap_score"]) for row in by_correction],
        "gap score",
        value_min=min(-0.1, min((row["gap_score"] for row in by_correction), default=0)),
        value_max=max(0.2, max((row["gap_score"] for row in by_correction), default=0)),
    )

    by_block_correction = group_weighted_mean(rows, ["block", "correction"], ["gap_score"])
    svg_heatmap(
        output_dir / "paper_gap_heatmap_by_block.svg",
        "Gap Heatmap by Evaluation Block and Correction",
        by_block_correction,
        "correction",
        "block",
        "gap_score",
    )

    if "pass_rate" in rows[0]:
        by_block_correction_pass = group_weighted_mean(rows, ["block", "correction"], ["pass_rate"])
        svg_heatmap(
            output_dir / "paper_pass_rate_heatmap_by_block.svg",
            "Pass Rate Heatmap by Evaluation Block and Correction",
            by_block_correction_pass,
            "correction",
            "block",
            "pass_rate",
            higher_is_bad=False,
        )


def main():
    parser = argparse.ArgumentParser(description="Plot ATS/AANA eval summaries.")
    parser.add_argument("--summary", default="eval_outputs/summary_by_condition.csv")
    parser.add_argument("--output-dir", default="eval_outputs")
    args = parser.parse_args()

    rows = read_csv(args.summary)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if try_matplotlib_plots(rows, output_dir):
        print("PNG plots saved.")
    else:
        svg_fallback_plots(rows, output_dir)
        print("matplotlib is not installed; SVG plots saved instead.")
    svg_report_plots(rows, output_dir)
    print("Paper-oriented SVG report plots saved.")


if __name__ == "__main__":
    main()
