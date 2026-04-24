import argparse
import csv
import pathlib
import statistics


def read_csv(path):
    with pathlib.Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fmean(rows, field):
    vals = [float(r[field]) for r in rows]
    return statistics.fmean(vals) if vals else 0.0


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
    for correction in ["baseline", "weak", "strong"]:
        subset = [r for r in rows if r["correction"] == correction]
        grouped = group_mean(subset, ["model"], ["gap_score"])
        plt.plot([r["model"] for r in grouped], [r["gap_score"] for r in grouped], marker="o", label=correction)
    plt.title("Gap vs Correction")
    plt.ylabel("Gap Score")
    plt.xticks(rotation=20, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "fig3_gap_correction.png")
    return True


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
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Arial" font-size="20">{title}</text>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#333"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#333"/>',
    ]
    for label in labels:
        x = x_pos(label)
        parts.append(f'<text x="{x}" y="{height-28}" text-anchor="middle" font-family="Arial" font-size="12">{label}</text>')
    for i, (name, points) in enumerate(series):
        color = colors[i % len(colors)]
        coords = " ".join(f"{x_pos(label)},{y_pos(value)}" for label, value in points)
        if coords:
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')
        for label, value in points:
            x, y = x_pos(label), y_pos(value)
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{width-margin-130}" y="{margin + i*20}" font-family="Arial" font-size="13" fill="{color}">{name}</text>')
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
    for correction in ["baseline", "weak", "strong"]:
        subset = [r for r in rows if r["correction"] == correction]
        grouped = group_mean(subset, ["model"], ["gap_score"])
        correction_series.append((correction, [(r["model"], r["gap_score"]) for r in grouped]))
    svg_line_plot(output_dir / "fig3_gap_correction.svg", "Gap vs Correction", correction_series)


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


if __name__ == "__main__":
    main()
