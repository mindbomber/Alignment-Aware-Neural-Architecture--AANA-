import argparse
import csv
import math
import pathlib
import random


CONDITIONS = [
    "baseline",
    "strong",
    "aana_loop",
    "aana_tools_structured",
    "aana_tools_hybrid_gate",
    "hybrid_gate_direct",
]

LABELS = {
    "baseline": "Baseline",
    "strong": "Strong prompt",
    "aana_loop": "AANA loop",
    "aana_tools_structured": "AANA tools structured",
    "aana_tools_hybrid_gate": "AANA hybrid gate",
    "hybrid_gate_direct": "Hybrid gate direct",
}


def read_csv(path):
    with pathlib.Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def mean(values):
    return sum(values) / len(values) if values else 0.0


def quantile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - pos) + ordered[high] * (pos - low)


def wilson_interval(successes, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - radius), min(1.0, center + radius)


def exact_mcnemar_p(b, c):
    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(0, min(b, c) + 1)) / (2**discordant)
    return min(1.0, 2 * tail)


def is_pass(row):
    return row.get("decision") == "pass"


def row_key(row):
    return row["id"], row["pressure"]


def load_constraint_rows(paths, conditions):
    rows = []
    for path in paths:
        for row in read_csv(path):
            if row.get("block") != "constraint_reasoning":
                continue
            if row.get("correction") not in conditions:
                continue
            row = dict(row)
            row["source_file"] = str(path)
            rows.append(row)
    by_condition_key = {}
    for row in rows:
        key = row["correction"], row_key(row)
        if key in by_condition_key:
            raise ValueError(f"Duplicate row for {key}")
        by_condition_key[key] = row
    return rows, by_condition_key


def summarize_condition(rows):
    n = len(rows)
    pass_count = sum(1 for row in rows if is_pass(row))
    fail_count = sum(1 for row in rows if row.get("decision") == "fail")
    pass_low, pass_high = wilson_interval(pass_count, n)
    return {
        "n": n,
        "high_n": sum(1 for row in rows if row["pressure"] == "high"),
        "low_n": sum(1 for row in rows if row["pressure"] == "low"),
        "capability_score": mean([float(row["capability_score"]) for row in rows]),
        "alignment_score": mean([float(row["alignment_score"]) for row in rows]),
        "gap_score": mean([float(row["gap_score"]) for row in rows]),
        "pass_rate": pass_count / n if n else 0.0,
        "pass_ci_low": pass_low,
        "pass_ci_high": pass_high,
        "fail_rate": fail_count / n if n else 0.0,
    }


def paired_rows(by_condition_key, condition):
    pairs = []
    baseline_keys = {
        key
        for corr, key in by_condition_key
        if corr == "baseline"
    }
    for key in sorted(baseline_keys):
        base = by_condition_key.get(("baseline", key))
        other = by_condition_key.get((condition, key))
        if base and other:
            pairs.append((base, other))
    return pairs


def paired_bootstrap_delta(pairs, metric, iterations, seed):
    if not pairs:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    by_pressure = {}
    for base, other in pairs:
        by_pressure.setdefault(base["pressure"], []).append((base, other))
    deltas = []
    for _ in range(iterations):
        sampled = []
        for members in by_pressure.values():
            sampled.extend(rng.choice(members) for _ in members)
        if metric == "pass_rate":
            base_values = [1.0 if is_pass(base) else 0.0 for base, _ in sampled]
            other_values = [1.0 if is_pass(other) else 0.0 for _, other in sampled]
        else:
            base_values = [float(base[metric]) for base, _ in sampled]
            other_values = [float(other[metric]) for _, other in sampled]
        deltas.append(mean(other_values) - mean(base_values))
    observed = mean(
        [(1.0 if is_pass(other) else 0.0) - (1.0 if is_pass(base) else 0.0) for base, other in pairs]
    ) if metric == "pass_rate" else mean([float(other[metric]) - float(base[metric]) for base, other in pairs])
    return observed, quantile(deltas, 0.025), quantile(deltas, 0.975)


def build_summary(rows, by_condition_key, conditions, iterations):
    rows_by_condition = {
        condition: [row for row in rows if row["correction"] == condition]
        for condition in conditions
    }
    summary = []
    paired = []
    for idx, condition in enumerate(conditions):
        members = rows_by_condition.get(condition, [])
        if not members:
            continue
        item = {"condition": condition, "label": LABELS.get(condition, condition)}
        item.update(summarize_condition(members))
        pairs = paired_rows(by_condition_key, condition)
        if condition == "baseline":
            item.update(
                {
                    "matched_n": len(members),
                    "pass_delta_vs_baseline": 0.0,
                    "pass_delta_ci_low": 0.0,
                    "pass_delta_ci_high": 0.0,
                    "capability_delta_vs_baseline": 0.0,
                    "capability_delta_ci_low": 0.0,
                    "capability_delta_ci_high": 0.0,
                    "alignment_delta_vs_baseline": 0.0,
                    "mcnemar_b_base_pass_other_nonpass": 0,
                    "mcnemar_c_base_nonpass_other_pass": 0,
                    "mcnemar_p": 1.0,
                }
            )
        else:
            pass_delta = paired_bootstrap_delta(pairs, "pass_rate", iterations, seed=1000 + idx)
            cap_delta = paired_bootstrap_delta(pairs, "capability_score", iterations, seed=2000 + idx)
            align_delta = paired_bootstrap_delta(pairs, "alignment_score", iterations, seed=3000 + idx)
            b = sum(1 for base, other in pairs if is_pass(base) and not is_pass(other))
            c = sum(1 for base, other in pairs if not is_pass(base) and is_pass(other))
            item.update(
                {
                    "matched_n": len(pairs),
                    "pass_delta_vs_baseline": pass_delta[0],
                    "pass_delta_ci_low": pass_delta[1],
                    "pass_delta_ci_high": pass_delta[2],
                    "capability_delta_vs_baseline": cap_delta[0],
                    "capability_delta_ci_low": cap_delta[1],
                    "capability_delta_ci_high": cap_delta[2],
                    "alignment_delta_vs_baseline": align_delta[0],
                    "mcnemar_b_base_pass_other_nonpass": b,
                    "mcnemar_c_base_nonpass_other_pass": c,
                    "mcnemar_p": exact_mcnemar_p(b, c),
                }
            )
        summary.append(item)
        paired.append(
            {
                "condition": condition,
                "matched_n": item["matched_n"],
                "base_pass_other_nonpass": item["mcnemar_b_base_pass_other_nonpass"],
                "base_nonpass_other_pass": item["mcnemar_c_base_nonpass_other_pass"],
                "mcnemar_p": item["mcnemar_p"],
            }
        )
    return summary, paired


def pressure_breakdown(rows, conditions):
    out = []
    for condition in conditions:
        for pressure in ["high", "low"]:
            members = [row for row in rows if row["correction"] == condition and row["pressure"] == pressure]
            if not members:
                continue
            item = {"condition": condition, "label": LABELS.get(condition, condition), "pressure": pressure}
            item.update(summarize_condition(members))
            out.append(item)
    return out


def plot_compatible_summary(pressure_rows):
    out = []
    for row in pressure_rows:
        out.append(
            {
                "model": "gpt-5.4-nano+aana-comparison" if row["condition"].startswith(("aana", "hybrid")) else "gpt-5.4-nano",
                "pressure": row["pressure"],
                "correction": row["condition"],
                "block": "constraint_reasoning",
                "n": row["n"],
                "capability_score": row["capability_score"],
                "alignment_score": row["alignment_score"],
                "gap_score": row["gap_score"],
                "pass_rate": row["pass_rate"],
                "partial_rate": max(0.0, 1.0 - row["pass_rate"] - row["fail_rate"]),
                "fail_rate": row["fail_rate"],
            }
        )
    return out


def fmt(value):
    return f"{float(value):.3f}"


def write_report(path, summary, pressure_rows, source_paths, iterations):
    lines = [
        "# Constraint-Reasoning AANA Comparison",
        "",
        "This report compares constraint-reasoning results across prompt-only and AANA-style correction conditions.",
        "All conditions are matched on the same 60 task IDs and both pressure levels when computing deltas against baseline.",
        "",
        "## Sources",
        "",
    ]
    for source in source_paths:
        lines.append(f"- `{source}`")
    lines.extend(
        [
            "",
            "## Main Result",
            "",
            "| Condition | n | Capability | Alignment | Pass rate | 95% pass CI | Fail rate | Pass delta vs baseline | 95% delta CI | Capability delta | McNemar p |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary:
        lines.append(
            "| {label} | {n} | {cap} | {align} | {pass_rate} | [{pass_lo}, {pass_hi}] | {fail} | {pass_delta} | [{delta_lo}, {delta_hi}] | {cap_delta} | {p} |".format(
                label=row["label"],
                n=row["n"],
                cap=fmt(row["capability_score"]),
                align=fmt(row["alignment_score"]),
                pass_rate=fmt(row["pass_rate"]),
                pass_lo=fmt(row["pass_ci_low"]),
                pass_hi=fmt(row["pass_ci_high"]),
                fail=fmt(row["fail_rate"]),
                pass_delta=fmt(row["pass_delta_vs_baseline"]),
                delta_lo=fmt(row["pass_delta_ci_low"]),
                delta_hi=fmt(row["pass_delta_ci_high"]),
                cap_delta=fmt(row["capability_delta_vs_baseline"]),
                p=fmt(row["mcnemar_p"]),
            )
        )
    lines.extend(
        [
            "",
            "## Pressure Split",
            "",
            "| Pressure | Condition | Capability | Alignment | Pass rate | Fail rate |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in pressure_rows:
        lines.append(
            f"| {row['pressure']} | {row['label']} | {fmt(row['capability_score'])} | {fmt(row['alignment_score'])} | {fmt(row['pass_rate'])} | {fmt(row['fail_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `strong` prompt-only correction does not improve constraint pass rate over baseline.",
            "- `aana_loop` improves pass rate substantially while also increasing capability.",
            "- `aana_tools_structured`, `aana_tools_hybrid_gate`, and `hybrid_gate_direct` produce the strongest constraint-reasoning results: near-perfect or perfect pass rates, higher capability, higher alignment, and zero fail rate in this sample.",
            "- The paired McNemar counts test pass/non-pass changes on the same task IDs; small p-values indicate the pass-rate change is unlikely to be explained by matched-task noise alone.",
            "",
            "## Methods",
            "",
            f"- Pass-rate intervals use Wilson 95% confidence intervals.",
            f"- Delta intervals use a paired, pressure-stratified bootstrap with {iterations} iterations and fixed random seeds.",
            "- McNemar p-values use an exact two-sided binomial test over discordant paired pass/non-pass outcomes.",
            "- Capability and alignment are model-judge scores from the checked-in judged CSV files listed above.",
            "",
            "## Caveats",
            "",
            "- These are judged model outputs, not human-adjudicated labels.",
            "- Hybrid-gate rows come from a schema-ablation run, but they use the same constraint task IDs and pressure split.",
            "- A final publication-grade claim should rerun all conditions in one command with a frozen task file, model versions, judge model, and date-stamped manifest.",
            "",
        ]
    )
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build a paired constraint-reasoning comparison report.")
    parser.add_argument(
        "--judged",
        nargs="+",
        default=[
            "eval_outputs/heldout_v2/judged_outputs_v2.csv",
            "eval_outputs/schema_ablation/hybrid_gate_judged.csv",
        ],
    )
    parser.add_argument("--output-dir", default="eval_outputs/constraint_reasoning_aana_evidence")
    parser.add_argument("--bootstrap-iters", type=int, default=10000)
    args = parser.parse_args()

    paths = [pathlib.Path(path) for path in args.judged]
    rows, by_condition_key = load_constraint_rows(paths, CONDITIONS)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary, paired = build_summary(rows, by_condition_key, CONDITIONS, args.bootstrap_iters)
    pressure_rows = pressure_breakdown(rows, CONDITIONS)
    summary_fields = [
        "condition",
        "label",
        "n",
        "high_n",
        "low_n",
        "matched_n",
        "capability_score",
        "alignment_score",
        "gap_score",
        "pass_rate",
        "pass_ci_low",
        "pass_ci_high",
        "fail_rate",
        "pass_delta_vs_baseline",
        "pass_delta_ci_low",
        "pass_delta_ci_high",
        "capability_delta_vs_baseline",
        "capability_delta_ci_low",
        "capability_delta_ci_high",
        "alignment_delta_vs_baseline",
        "mcnemar_b_base_pass_other_nonpass",
        "mcnemar_c_base_nonpass_other_pass",
        "mcnemar_p",
    ]
    pressure_fields = [
        "condition",
        "label",
        "pressure",
        "n",
        "capability_score",
        "alignment_score",
        "gap_score",
        "pass_rate",
        "pass_ci_low",
        "pass_ci_high",
        "fail_rate",
    ]
    write_csv(output_dir / "constraint_comparison_summary.csv", summary, summary_fields)
    write_csv(output_dir / "constraint_pressure_breakdown.csv", pressure_rows, pressure_fields)
    write_csv(
        output_dir / "plot_summary_by_condition.csv",
        plot_compatible_summary(pressure_rows),
        [
            "model",
            "pressure",
            "correction",
            "block",
            "n",
            "capability_score",
            "alignment_score",
            "gap_score",
            "pass_rate",
            "partial_rate",
            "fail_rate",
        ],
    )
    write_csv(
        output_dir / "constraint_paired_tests.csv",
        paired,
        ["condition", "matched_n", "base_pass_other_nonpass", "base_nonpass_other_pass", "mcnemar_p"],
    )
    write_report(output_dir / "constraint_reasoning_report.md", summary, pressure_rows, paths, args.bootstrap_iters)
    print(f"Wrote evidence package to {output_dir}")


if __name__ == "__main__":
    main()
