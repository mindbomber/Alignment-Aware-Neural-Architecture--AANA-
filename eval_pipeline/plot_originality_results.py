import argparse
import csv
import pathlib
import statistics


ORDER = ["baseline", "originality_aana"]
LABELS = {
    "baseline": "Baseline",
    "originality_aana": "Originality AANA",
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
            "novelty": mean([float(row["novelty_score"]) for row in group]),
            "viable_originality": mean([float(row["viable_originality_score"]) for row in group]),
            "pass_rate": mean([row["decision"] == "pass" for row in group]),
        }
    return metrics


def write_svg(path, title, series, metrics, order):
    width = max(760, 140 + len(order) * 230)
    height = 430
    left = 80
    top = 52
    chart_h = 285
    bar_w = 42
    group_gap = 80
    colors = ["#2f6f8f", "#b15b39", "#6d8f3f", "#7952b3", "#64748b"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="30" font-family="Arial" font-size="20" font-weight="700">{title}</text>',
    ]
    for tick in range(0, 6):
        value = tick / 5
        y = top + chart_h - value * chart_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - 50}" y2="{y:.1f}" stroke="#e7e7e7"/>')
        parts.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{value:.1f}</text>')
    for idx, condition in enumerate(order):
        x0 = left + idx * (bar_w * len(series) + group_gap)
        for s_idx, (key, _) in enumerate(series):
            value = metrics[condition][key]
            h = value * chart_h
            x = x0 + s_idx * (bar_w + 7)
            y = top + chart_h - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="{colors[s_idx % len(colors)]}"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.2f}</text>')
        parts.append(
            f'<text x="{x0 + (bar_w * len(series)) / 2:.1f}" y="{top + chart_h + 35}" text-anchor="middle" '
            f'font-family="Arial" font-size="12">{LABELS.get(condition, condition)}</text>'
        )
    for s_idx, (_, label) in enumerate(series):
        x = left + s_idx * 155
        y = height - 32
        parts.append(f'<rect x="{x}" y="{y - 12}" width="13" height="13" fill="{colors[s_idx % len(colors)]}"/>')
        parts.append(f'<text x="{x + 19}" y="{y - 1}" font-family="Arial" font-size="12">{label}</text>')
    parts.append("</svg>")
    pathlib.Path(path).write_text("\n".join(parts), encoding="utf-8")


def write_table(path, metrics, order):
    fields = ["condition", "n", "capability", "alignment", "novelty", "viable_originality", "pass_rate"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for condition in order:
            row = {"condition": condition, **metrics[condition]}
            writer.writerow({key: round(value, 4) if isinstance(value, float) else value for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description="Plot AANA originality results.")
    parser.add_argument("--judged", default="eval_outputs/originality/originality_judged.csv")
    parser.add_argument("--output-dir", default="eval_outputs/originality/report_visuals")
    args = parser.parse_args()

    rows = load_rows(args.judged)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    order = condition_order(rows)
    metrics = grouped_metrics(rows, order)
    write_table(output_dir / "originality_metrics.csv", metrics, order)
    write_svg(
        output_dir / "originality_metrics.svg",
        "AANA Originality: Viable Novelty Under Constraints",
        [
            ("capability", "Capability"),
            ("alignment", "Alignment"),
            ("novelty", "Novelty"),
            ("viable_originality", "Viable originality"),
            ("pass_rate", "Pass rate"),
        ],
        metrics,
        order,
    )
    print(f"Wrote originality visuals to {output_dir}")


if __name__ == "__main__":
    main()
