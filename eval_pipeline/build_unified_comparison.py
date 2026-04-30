import argparse
import collections
import csv
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys


DEFAULT_CONDITIONS = [
    "baseline",
    "strong",
    "aana_loop",
    "aana_tools_structured",
    "aana_tools_hybrid_gate",
    "hybrid_gate_direct",
]

DEFAULT_JUDGED = [
    "eval_outputs/heldout_v2/judged_outputs_v2.csv",
    "eval_outputs/schema_ablation/hybrid_gate_judged.csv",
]

REQUIRED_COLUMNS = [
    "id",
    "block",
    "task_type",
    "model",
    "pressure",
    "correction",
    "capability_score",
    "alignment_score",
    "gap_score",
    "decision",
]

SUMMARY_FIELDS = [
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
]


def read_csv(path):
    with pathlib.Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def mean(values):
    return round(sum(values) / len(values), 4) if values else 0.0


def validate_columns(rows, source):
    if not rows:
        raise ValueError(f"No rows found in {source}")
    missing = [column for column in REQUIRED_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError(f"{source} is missing required columns: {', '.join(missing)}")


def load_rows(judged_paths, conditions, block):
    rows = []
    sources = []
    for judged_path in judged_paths:
        path = pathlib.Path(judged_path)
        source_rows = read_csv(path)
        validate_columns(source_rows, path)
        source_count = 0
        for row in source_rows:
            if row["block"] != block:
                continue
            if row["correction"] not in conditions:
                continue
            item = dict(row)
            item["source_file"] = str(path)
            rows.append(item)
            source_count += 1
        sources.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "matched_rows": source_count,
            }
        )
    return rows, sources


def row_key(row):
    return row["id"], row["pressure"]


def index_by_condition(rows):
    indexed = {}
    duplicates = []
    for row in rows:
        key = row["correction"], row_key(row)
        if key in indexed:
            duplicates.append(key)
        indexed[key] = row
    if duplicates:
        sample = ", ".join(f"{condition}:{task_id}/{pressure}" for condition, (task_id, pressure) in duplicates[:5])
        raise ValueError(f"Duplicate condition/task/pressure rows: {sample}")
    return indexed


def validate_matched_rows(rows, conditions, pressures):
    keys_by_condition = {
        condition: {row_key(row) for row in rows if row["correction"] == condition}
        for condition in conditions
    }
    missing_conditions = [condition for condition, keys in keys_by_condition.items() if not keys]
    if missing_conditions:
        raise ValueError(f"Missing conditions: {', '.join(missing_conditions)}")

    expected = keys_by_condition[conditions[0]]
    errors = []
    for condition in conditions[1:]:
        missing = sorted(expected - keys_by_condition[condition])
        extra = sorted(keys_by_condition[condition] - expected)
        if missing:
            errors.append(f"{condition} missing {len(missing)} rows, e.g. {missing[:3]}")
        if extra:
            errors.append(f"{condition} has {len(extra)} extra rows, e.g. {extra[:3]}")

    observed_pressures = sorted({pressure for _, pressure in expected})
    if observed_pressures != sorted(pressures):
        errors.append(f"Expected pressures {pressures}, found {observed_pressures}")

    task_ids = {task_id for task_id, _ in expected}
    for task_id in sorted(task_ids):
        task_pressures = {pressure for key_task_id, pressure in expected if key_task_id == task_id}
        if task_pressures != set(pressures):
            errors.append(f"{task_id} has pressure levels {sorted(task_pressures)}")
            break

    if errors:
        raise ValueError("Unified comparison validation failed:\n- " + "\n- ".join(errors))
    return expected


def summary(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["model"], row["pressure"], row["correction"], row["block"])].append(row)
    out = []
    for (model, pressure, correction, block), members in sorted(groups.items()):
        decisions = [row["decision"] for row in members]
        out.append(
            {
                "model": model,
                "pressure": pressure,
                "correction": correction,
                "block": block,
                "n": len(members),
                "capability_score": mean([float(row["capability_score"]) for row in members]),
                "alignment_score": mean([float(row["alignment_score"]) for row in members]),
                "gap_score": mean([float(row["gap_score"]) for row in members]),
                "pass_rate": mean([1.0 if decision == "pass" else 0.0 for decision in decisions]),
                "partial_rate": mean([1.0 if decision == "partial" else 0.0 for decision in decisions]),
                "fail_rate": mean([1.0 if decision == "fail" else 0.0 for decision in decisions]),
            }
        )
    return out


def ordered_rows(rows, conditions):
    condition_index = {condition: idx for idx, condition in enumerate(conditions)}
    return sorted(
        rows,
        key=lambda row: (
            row["id"],
            row["pressure"],
            condition_index.get(row["correction"], 999),
        ),
    )


def fieldnames(rows):
    preferred = [
        "id",
        "block",
        "task_type",
        "model",
        "pressure",
        "correction",
        "capability_prompt",
        "prompt",
        "reference_notes",
        "response_text",
        "api_response_id",
        "api_error",
        "aana_trace",
        "judge_model",
        "capability_score",
        "alignment_score",
        "gap_score",
        "decision",
        "rationale",
        "judge_error",
        "source_file",
    ]
    present = set()
    for row in rows:
        present.update(row)
    return [field for field in preferred if field in present] + sorted(present - set(preferred))


def write_manifest(path, *, args, matched_keys, sources, outputs, task_hash):
    manifest = {
        "name": "Unified AANA comparison preflight",
        "generated_at_utc": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo_commit_sha": git_commit(),
        "block": args.block,
        "conditions": args.conditions,
        "pressures": args.pressures,
        "task_count": len({task_id for task_id, _ in matched_keys}),
        "row_count_per_condition": len(matched_keys),
        "total_rows": len(matched_keys) * len(args.conditions),
        "strict_validation": True,
        "source_files": sources,
        "task_file": {
            "path": args.tasks,
            "sha256": task_hash,
        } if args.tasks else None,
        "outputs": outputs,
        "live_rerun_issue": "https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/issues/2",
        "notes": [
            "This preflight artifact validates matched rows from existing judged outputs.",
            "It does not make live model calls.",
            "Use this structure for the next unified same-run rerun.",
        ],
    }
    pathlib.Path(path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_report(path, summary_rows, conditions):
    by_condition = collections.defaultdict(list)
    for row in summary_rows:
        by_condition[row["correction"]].append(row)

    lines = [
        "# Unified AANA Comparison Preflight",
        "",
        "This preflight validates that the compared conditions share the same task IDs and pressure levels.",
        "It is built from existing judged outputs and is intended to de-risk the next live unified rerun.",
        "",
        "| Condition | n | Capability | Alignment | Pass rate | Fail rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for condition in conditions:
        members = by_condition[condition]
        n = sum(int(row["n"]) for row in members)
        weighted = lambda field: sum(float(row[field]) * int(row["n"]) for row in members) / n
        lines.append(
            f"| {condition} | {n} | {weighted('capability_score'):.3f} | {weighted('alignment_score'):.3f} | {weighted('pass_rate'):.3f} | {weighted('fail_rate'):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "Use the same output layout for a live unified same-run comparison where all six conditions are generated and judged from one frozen task file and one dated manifest.",
            "",
        ]
    )
    pathlib.Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_command_plan(path, args):
    content = f"""# Unified same-run command plan
# Review model names and token limits before running. These commands may make API calls.

$out = "{args.output_dir}"
New-Item -ItemType Directory -Force -Path $out | Out-Null

python eval_pipeline/run_evals.py --tasks {args.tasks or '<TASK_FILE>'} --output "$out/raw_prompt_outputs.jsonl" --models gpt-5.4-nano --pressures low high --corrections baseline strong

python eval_pipeline/run_aana_evals.py --tasks {args.tasks or '<TASK_FILE>'} --output "$out/aana_loop_outputs.jsonl" --pressures low high --ablation-mode loop --condition-name aana_loop

python eval_pipeline/run_aana_evals.py --tasks {args.tasks or '<TASK_FILE>'} --output "$out/aana_tools_structured_outputs.jsonl" --pressures low high --ablation-mode structured --condition-name aana_tools_structured

python eval_pipeline/run_aana_evals.py --tasks {args.tasks or '<TASK_FILE>'} --output "$out/aana_tools_hybrid_gate_outputs.jsonl" --pressures low high --ablation-mode hybrid_gate --condition-name aana_tools_hybrid_gate

python eval_pipeline/run_aana_evals.py --tasks {args.tasks or '<TASK_FILE>'} --output "$out/hybrid_gate_direct_outputs.jsonl" --pressures low high --ablation-mode hybrid_gate_direct --condition-name hybrid_gate_direct

python eval_pipeline/merge_jsonl.py --output "$out/raw_outputs.jsonl" "$out/raw_prompt_outputs.jsonl" "$out/aana_loop_outputs.jsonl" "$out/aana_tools_structured_outputs.jsonl" "$out/aana_tools_hybrid_gate_outputs.jsonl" "$out/hybrid_gate_direct_outputs.jsonl"

python eval_pipeline/judge_score_outputs.py --input "$out/raw_outputs.jsonl" --judge-jsonl "$out/judge_scores.jsonl" --judged "$out/judged_outputs.csv" --summary "$out/summary_by_condition.csv"

python eval_pipeline/build_unified_comparison.py --judged "$out/judged_outputs.csv" --output-dir "$out" --tasks {args.tasks or '<TASK_FILE>'}

python eval_pipeline/plot_results.py --summary "$out/summary_by_condition.csv" --output-dir "$out/plots"
"""
    pathlib.Path(path).write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build and validate a unified AANA comparison artifact set.")
    parser.add_argument("--judged", nargs="+", default=DEFAULT_JUDGED)
    parser.add_argument("--output-dir", default="eval_outputs/unified_aana_comparison_preflight")
    parser.add_argument("--tasks", default="eval_outputs/heldout/heldout_ats_aana_tasks.jsonl")
    parser.add_argument("--block", default="constraint_reasoning")
    parser.add_argument("--conditions", nargs="+", default=DEFAULT_CONDITIONS)
    parser.add_argument("--pressures", nargs="+", default=["low", "high"])
    args = parser.parse_args()

    rows, sources = load_rows(args.judged, args.conditions, args.block)
    matched_keys = validate_matched_rows(rows, args.conditions, args.pressures)
    index_by_condition(rows)

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    judged_path = output_dir / "judged_outputs.csv"
    summary_path = output_dir / "summary_by_condition.csv"
    manifest_path = output_dir / "manifest.json"
    report_path = output_dir / "report.md"
    command_plan_path = output_dir / "command_plan.ps1"

    selected_rows = ordered_rows(rows, args.conditions)
    summary_rows = summary(selected_rows)
    write_csv(judged_path, selected_rows, fieldnames(selected_rows))
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    write_report(report_path, summary_rows, args.conditions)
    write_command_plan(command_plan_path, args)

    task_hash = ""
    if args.tasks and pathlib.Path(args.tasks).exists():
        task_hash = sha256_file(args.tasks)
    outputs = [
        {"path": str(judged_path), "sha256": sha256_file(judged_path)},
        {"path": str(summary_path), "sha256": sha256_file(summary_path)},
        {"path": str(report_path), "sha256": sha256_file(report_path)},
        {"path": str(command_plan_path), "sha256": sha256_file(command_plan_path)},
    ]
    write_manifest(
        manifest_path,
        args=args,
        matched_keys=matched_keys,
        sources=sources,
        outputs=outputs,
        task_hash=task_hash,
    )
    print(f"Wrote unified comparison preflight to {output_dir}")
    print(f"Validated {len(matched_keys)} task/pressure rows per condition across {len(args.conditions)} conditions.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
