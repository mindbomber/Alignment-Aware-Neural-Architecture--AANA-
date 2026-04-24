import argparse
import csv
import pathlib
import statistics


ORDER = [
    "aana_loop_750",
    "aana_tools_detect_only",
    "aana_tools_generic_repair",
    "aana_tools_structured",
    "structured_direct",
    "aana_tools_schema",
    "schema_direct",
    "aana_tools_hybrid",
    "hybrid_direct",
    "aana_tools_hybrid_gate",
    "hybrid_gate_direct",
]

LABELS = {
    "aana_loop_750": "Loop 750",
    "aana_tools_detect_only": "Detect only",
    "aana_tools_generic_repair": "Generic repair",
    "aana_tools_structured": "Structured",
    "structured_direct": "Direct repair",
    "aana_tools_schema": "Schema loop",
    "schema_direct": "Schema direct",
    "aana_tools_hybrid": "Hybrid loop",
    "hybrid_direct": "Hybrid direct",
    "aana_tools_hybrid_gate": "Hybrid gate",
    "hybrid_gate_direct": "Gate direct",
}


def mean(values):
    return statistics.fmean(values) if values else 0.0


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def condition_order(rows):
    present = {row["correction"] for row in rows}
    ordered = [condition for condition in ORDER if condition in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def grouped_metrics(rows, order):
    metrics = {}
    for condition in order:
        group = [row for row in rows if row["correction"] == condition]
        metrics[condition] = {
            "n": len(group),
            "capability": mean([float(row["capability_score"]) for row in group]),
            "alignment": mean([float(row["alignment_score"]) for row in group]),
            "pass_rate": mean([row["decision"] == "pass" for row in group]),
            "low_pass": mean([row["decision"] == "pass" for row in group if row["pressure"] == "low"]),
            "high_pass": mean([row["decision"] == "pass" for row in group if row["pressure"] == "high"]),
        }
    return metrics


def write_svg(path, title, series, order):
    width = max(980, 150 + len(order) * 170)
    height = 430
    left = 80
    top = 52
    chart_h = 285
    chart_w = width - 130
    bar_w = 58
    group_gap = 110
    colors = ["#2f6f8f", "#b15b39", "#6d8f3f"]

    max_value = 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="30" font-family="Arial" font-size="20" font-weight="700">{title}</text>',
    ]
    for tick in range(0, 6):
        value = tick / 5
        y = top + chart_h - value / max_value * chart_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_w}" y2="{y:.1f}" stroke="#e7e7e7"/>')
        parts.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{value:.1f}</text>')

    for idx, condition in enumerate(order):
        x0 = left + idx * (bar_w * len(series) + group_gap)
        for s_idx, (key, label) in enumerate(series):
            value = grouped[condition][key]
            h = value / max_value * chart_h
            x = x0 + s_idx * (bar_w + 7)
            y = top + chart_h - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="{colors[s_idx % len(colors)]}"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="11">{value:.2f}</text>')
        parts.append(
            f'<text x="{x0 + (bar_w * len(series)) / 2:.1f}" y="{top + chart_h + 35}" text-anchor="middle" '
            f'font-family="Arial" font-size="12">{LABELS.get(condition, condition)}</text>'
        )

    legend_x = left
    legend_y = height - 32
    for s_idx, (_, label) in enumerate(series):
        x = legend_x + s_idx * 165
        parts.append(f'<rect x="{x}" y="{legend_y - 12}" width="13" height="13" fill="{colors[s_idx % len(colors)]}"/>')
        parts.append(f'<text x="{x + 19}" y="{legend_y - 1}" font-family="Arial" font-size="12">{label}</text>')
    parts.append("</svg>")
    pathlib.Path(path).write_text("\n".join(parts), encoding="utf-8")


def write_table(path, metrics, order):
    fields = ["condition", "n", "capability", "alignment", "pass_rate", "low_pass", "high_pass"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for condition in order:
            row = {"condition": condition, **metrics[condition]}
            writer.writerow({key: round(value, 4) if isinstance(value, float) else value for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description="Plot constraint ablation results.")
    parser.add_argument("--judged", default="eval_outputs/ablation/constraint_ablation_judged.csv")
    parser.add_argument("--output-dir", default="eval_outputs/ablation/report_visuals")
    args = parser.parse_args()

    rows = load_rows(args.judged)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    global grouped
    order = condition_order(rows)
    grouped = grouped_metrics(rows, order)
    write_table(output_dir / "ablation_metrics.csv", grouped, order)
    write_svg(
        output_dir / "ablation_capability_alignment_pass.svg",
        "Constraint Ablation: Capability, Alignment, Pass Rate",
        [("capability", "Capability"), ("alignment", "Alignment"), ("pass_rate", "Pass rate")],
        order,
    )
    write_svg(
        output_dir / "ablation_pressure_pass.svg",
        "Constraint Ablation: Pass Rate by Pressure",
        [("low_pass", "Low pressure"), ("high_pass", "High pressure")],
        order,
    )
    print(f"Wrote ablation visuals to {output_dir}")


if __name__ == "__main__":
    main()
