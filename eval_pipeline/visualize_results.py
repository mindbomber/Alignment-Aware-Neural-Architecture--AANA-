import argparse
import csv
import pathlib
import statistics


ORDER = [
    "baseline",
    "weak",
    "strong",
    "aana_loop",
    "aana_tools_v1",
    "aana_tools_structured",
]

LABELS = {
    "baseline": "Baseline",
    "weak": "Weak Prompt",
    "strong": "Strong Prompt",
    "aana_loop": "AANA Loop",
    "aana_tools_v1": "AANA Tools v1",
    "aana_tools_structured": "AANA Structured",
}

BLOCKS = ["truthfulness", "constraint_reasoning", "proxy_trap", "recovery", "abstention"]


def read_rows(path):
    with pathlib.Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def weighted(rows, field):
    total = sum(int(r["n"]) for r in rows)
    return sum(float(r[field]) * int(r["n"]) for r in rows) / total if total else 0


def grouped(rows, fields):
    out = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        out.setdefault(key, []).append(row)
    return out


def svg_header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111827}.small{font-size:12px}.label{font-size:13px}.title{font-size:22px;font-weight:700}.axis{stroke:#374151;stroke-width:1}.grid{stroke:#e5e7eb;stroke-width:1}.note{fill:#4b5563;font-size:12px}</style>',
    ]


def svg_footer():
    return ["</svg>"]


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def color_scale(value, low=0.2, high=1.0):
    t = max(0, min(1, (value - low) / (high - low)))
    # red -> amber -> green
    if t < 0.5:
        u = t / 0.5
        r, g, b = 220, int(75 + 115 * u), 60
    else:
        u = (t - 0.5) / 0.5
        r, g, b = int(245 - 210 * u), int(190 - 45 * u), int(65 + 55 * u)
    return f"rgb({r},{g},{b})"


def bar_chart(path, title, data, y_max=1.0):
    width, height = 980, 520
    left, right, top, bottom = 80, 40, 70, 110
    plot_w = width - left - right
    plot_h = height - top - bottom
    parts = svg_header(width, height)
    parts.append(f'<text class="title" x="{width/2}" y="34" text-anchor="middle">{esc(title)}</text>')

    for i in range(6):
        y = top + plot_h - (i / 5) * plot_h
        val = (i / 5) * y_max
        parts.append(f'<line class="grid" x1="{left}" y1="{y}" x2="{width-right}" y2="{y}"/>')
        parts.append(f'<text class="small" x="{left-10}" y="{y+4}" text-anchor="end">{val:.1f}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}"/>')

    group_w = plot_w / len(data)
    bar_w = min(58, group_w * 0.58)
    for i, (label, value) in enumerate(data):
        x = left + i * group_w + (group_w - bar_w) / 2
        h = (value / y_max) * plot_h
        y = top + plot_h - h
        color = "#2563eb" if "AANA" not in label else "#059669"
        if "Structured" in label:
            color = "#047857"
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="3"/>')
        parts.append(f'<text class="label" x="{x+bar_w/2}" y="{y-8}" text-anchor="middle">{value:.3f}</text>')
        parts.append(f'<text class="small" x="{x+bar_w/2}" y="{top+plot_h+22}" text-anchor="middle">{esc(label)}</text>')
    pathlib.Path(path).write_text("\n".join(parts + svg_footer()), encoding="utf-8")


def grouped_bar_chart(path, title, series):
    width, height = 1060, 540
    left, right, top, bottom = 80, 160, 70, 100
    plot_w = width - left - right
    plot_h = height - top - bottom
    colors = {"low": "#2563eb", "high": "#dc2626"}
    conditions = [c for c in ORDER if c in {k[1] for k in series}]
    parts = svg_header(width, height)
    parts.append(f'<text class="title" x="{width/2}" y="34" text-anchor="middle">{esc(title)}</text>')
    for i in range(6):
        y = top + plot_h - (i / 5) * plot_h
        parts.append(f'<line class="grid" x1="{left}" y1="{y}" x2="{width-right}" y2="{y}"/>')
        parts.append(f'<text class="small" x="{left-10}" y="{y+4}" text-anchor="end">{i/5:.1f}</text>')
    group_w = plot_w / len(conditions)
    bar_w = min(34, group_w * 0.32)
    for i, cond in enumerate(conditions):
        cx = left + i * group_w + group_w / 2
        for j, pressure in enumerate(["low", "high"]):
            value = series.get((pressure, cond), 0)
            h = value * plot_h
            x = cx + (j - 0.5) * bar_w
            y = top + plot_h - h
            parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{colors[pressure]}" rx="3"/>')
        parts.append(f'<text class="small" x="{cx}" y="{top+plot_h+22}" text-anchor="middle">{esc(LABELS.get(cond, cond))}</text>')
    parts.append(f'<rect x="{width-right+25}" y="{top+10}" width="14" height="14" fill="{colors["low"]}"/><text class="small" x="{width-right+46}" y="{top+22}">Low pressure</text>')
    parts.append(f'<rect x="{width-right+25}" y="{top+34}" width="14" height="14" fill="{colors["high"]}"/><text class="small" x="{width-right+46}" y="{top+46}">High pressure</text>')
    pathlib.Path(path).write_text("\n".join(parts + svg_footer()), encoding="utf-8")


def heatmap(path, title, matrix):
    width, height = 1120, 520
    left, top = 210, 80
    cell_w, cell_h = 132, 58
    parts = svg_header(width, height)
    parts.append(f'<text class="title" x="{width/2}" y="34" text-anchor="middle">{esc(title)}</text>')
    conditions = [c for c in ORDER if any((block, c) in matrix for block in BLOCKS)]
    for j, cond in enumerate(conditions):
        x = left + j * cell_w + cell_w / 2
        parts.append(f'<text class="small" x="{x}" y="{top-18}" text-anchor="middle">{esc(LABELS.get(cond, cond))}</text>')
    for i, block in enumerate(BLOCKS):
        y = top + i * cell_h
        parts.append(f'<text class="label" x="{left-12}" y="{y+cell_h/2+5}" text-anchor="end">{esc(block)}</text>')
        for j, cond in enumerate(conditions):
            value = matrix.get((block, cond), 0)
            x = left + j * cell_w
            color = color_scale(value)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h-4}" fill="{color}" rx="3"/>')
            parts.append(f'<text class="label" x="{x+(cell_w-4)/2}" y="{y+cell_h/2+5}" text-anchor="middle">{value:.3f}</text>')
    pathlib.Path(path).write_text("\n".join(parts + svg_footer()), encoding="utf-8")


def delta_chart(path, title, deltas):
    data = [(LABELS.get(k, k), v) for k, v in deltas]
    width, height = 940, 460
    left, right, top, bottom = 90, 40, 70, 100
    plot_w = width - left - right
    plot_h = height - top - bottom
    min_v = min(0, min(v for _, v in data))
    max_v = max(0.1, max(v for _, v in data))
    parts = svg_header(width, height)
    parts.append(f'<text class="title" x="{width/2}" y="34" text-anchor="middle">{esc(title)}</text>')
    zero_y = top + plot_h - (0 - min_v) / (max_v - min_v) * plot_h
    parts.append(f'<line class="axis" x1="{left}" y1="{zero_y}" x2="{width-right}" y2="{zero_y}"/>')
    group_w = plot_w / len(data)
    bar_w = min(58, group_w * 0.58)
    for i, (label, value) in enumerate(data):
        x = left + i * group_w + (group_w - bar_w) / 2
        y_val = top + plot_h - (value - min_v) / (max_v - min_v) * plot_h
        y = min(y_val, zero_y)
        h = abs(zero_y - y_val)
        color = "#059669" if value >= 0 else "#dc2626"
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="3"/>')
        parts.append(f'<text class="label" x="{x+bar_w/2}" y="{y-8 if value >= 0 else y+h+18}" text-anchor="middle">{value:+.3f}</text>')
        parts.append(f'<text class="small" x="{x+bar_w/2}" y="{height-42}" text-anchor="middle">{esc(label)}</text>')
    pathlib.Path(path).write_text("\n".join(parts + svg_footer()), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Create SVG visualizations for ATS/AANA eval results.")
    parser.add_argument("--summary", default="eval_outputs/judge_summary_full_comparison.csv")
    parser.add_argument("--output-dir", default="eval_outputs/report_visuals")
    args = parser.parse_args()

    rows = read_rows(args.summary)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    by_correction = grouped(rows, ["correction"])
    pass_data = []
    align_data = []
    for corr in ORDER:
        members = by_correction.get((corr,), [])
        if members:
            pass_data.append((LABELS[corr], weighted(members, "pass_rate")))
            align_data.append((LABELS[corr], weighted(members, "alignment_score")))
    bar_chart(output_dir / "overall_pass_rate.svg", "Overall Pass Rate by Condition", pass_data)
    bar_chart(output_dir / "overall_alignment_score.svg", "Overall Alignment Score by Condition", align_data)

    by_pressure_correction = grouped(rows, ["pressure", "correction"])
    pressure_series = {
        key: weighted(members, "pass_rate") for key, members in by_pressure_correction.items()
    }
    grouped_bar_chart(output_dir / "pass_rate_by_pressure.svg", "Pass Rate by Pressure and Condition", pressure_series)

    by_block_correction = grouped(rows, ["block", "correction"])
    pass_matrix = {
        key: weighted(members, "pass_rate") for key, members in by_block_correction.items()
    }
    align_matrix = {
        key: weighted(members, "alignment_score") for key, members in by_block_correction.items()
    }
    heatmap(output_dir / "block_pass_rate_heatmap.svg", "Pass Rate Heatmap by Block and Condition", pass_matrix)
    heatmap(output_dir / "block_alignment_heatmap.svg", "Alignment Score Heatmap by Block and Condition", align_matrix)

    baseline = weighted(by_correction[("baseline",)], "pass_rate")
    deltas = []
    for corr in ORDER:
        if corr == "baseline":
            continue
        members = by_correction.get((corr,), [])
        if members:
            deltas.append((corr, weighted(members, "pass_rate") - baseline))
    delta_chart(output_dir / "pass_rate_delta_vs_baseline.svg", "Pass Rate Delta vs Baseline", deltas)

    print(f"Wrote visualizations to {output_dir}")


if __name__ == "__main__":
    main()
