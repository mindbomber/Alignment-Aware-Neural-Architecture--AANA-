import argparse
import csv
import json
import pathlib


ORDER = ["baseline", "pressure_only", "weak_correction", "strong_aana"]


def read_csv(path):
    with pathlib.Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_report(path, rows):
    by_condition = {row["condition"]: row for row in rows}
    lines = [
        "# Table 2 Pilot Results",
        "",
        "This pilot replaces the synthetic Table 2 shape with real model outputs.",
        "",
        "| Condition | Pressure | n | Capability | Alignment | Delta | Violation Rate |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for condition in ORDER:
        row = by_condition.get(condition)
        if not row:
            continue
        lines.append(
            "| {condition} | {pressure} | {n} | {capability} | {alignment} | {delta} | {violation} |".format(
                condition=condition,
                pressure=row["pressure"],
                n=row["n"],
                capability=f"{float(row['capability_score']):.3f}",
                alignment=f"{float(row['alignment_score']):.3f}",
                delta=f"{float(row['delta_score']):.3f}",
                violation=f"{float(row['violation_rate']):.3f}",
            )
        )

    baseline = by_condition.get("baseline")
    pressure = by_condition.get("pressure_only")
    strong = by_condition.get("strong_aana")
    if baseline and pressure and strong:
        pressure_delta = float(pressure["delta_score"])
        baseline_delta = float(baseline["delta_score"])
        strong_delta = float(strong["delta_score"])
        pressure_violation = float(pressure["violation_rate"])
        strong_violation = float(strong["violation_rate"])
        lines.extend(
            [
                "",
                "## Directional Tests",
                "",
                f"- Delta pressure-only > baseline: `{pressure_delta:.3f} > {baseline_delta:.3f}` -> `{pressure_delta > baseline_delta}`",
                f"- Delta strong AANA < pressure-only: `{strong_delta:.3f} < {pressure_delta:.3f}` -> `{strong_delta < pressure_delta}`",
                f"- Violation rate strong AANA < pressure-only: `{strong_violation:.3f} < {pressure_violation:.3f}` -> `{strong_violation < pressure_violation}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Caveat",
            "",
            "This is a small pilot intended to test the predicted direction of the effect, not a final benchmark.",
            "",
        ]
    )
    pathlib.Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_manifest(path, args, rows):
    manifest = {
        "name": "Table 2 pilot",
        "tasks": args.tasks,
        "raw_outputs": args.raw_outputs,
        "judged_outputs": args.judged,
        "summary": args.summary,
        "conditions": ORDER,
        "n_conditions": len(rows),
        "n_outputs": sum(int(row["n"]) for row in rows),
        "alignment_formula": "mean(P_truth_grounding, B_constraint_adherence, C_task_coherence, F_feedback_awareness)",
        "delta_formula": "capability_score - alignment_score",
        "manual_spotcheck": args.spotcheck,
    }
    pathlib.Path(path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Write the Table 2 pilot report and manifest.")
    parser.add_argument("--tasks", default="eval_outputs/pilot_table2/pilot_tasks.jsonl")
    parser.add_argument("--raw-outputs", default="eval_outputs/pilot_table2/raw_outputs.jsonl")
    parser.add_argument("--judged", default="eval_outputs/pilot_table2/judged_outputs.csv")
    parser.add_argument("--summary", default="eval_outputs/pilot_table2/table2_pilot_summary.csv")
    parser.add_argument("--spotcheck", default="eval_outputs/pilot_table2/manual_spotcheck_sample.csv")
    parser.add_argument("--report", default="eval_outputs/pilot_table2/report.md")
    parser.add_argument("--manifest", default="eval_outputs/pilot_table2/manifest.json")
    args = parser.parse_args()

    rows = read_csv(args.summary)
    write_report(args.report, rows)
    write_manifest(args.manifest, args, rows)
    print(f"Wrote {args.report}")
    print(f"Wrote {args.manifest}")


if __name__ == "__main__":
    main()
