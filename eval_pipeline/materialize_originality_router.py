import argparse
import collections
import csv
import json
import pathlib
import statistics


ROUTED_AANA_TASK_TYPES = {"originality_product", "originality_theory"}
ROUTED_CONDITION = "originality_routed"


def read_jsonl(path):
    rows = []
    with pathlib.Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path):
    with pathlib.Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_jsonl(path, rows):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path, rows):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def mean(values):
    return round(statistics.fmean(values), 4) if values else 0.0


def source_condition(task_type):
    if task_type in ROUTED_AANA_TASK_TYPES:
        return "originality_aana"
    return "baseline"


def routed_model(generator_model):
    return f"{generator_model}+{ROUTED_CONDITION}"


def route_trace(task_type, source):
    if source == "originality_aana":
        reason = "Full v6 evaluation showed positive viable-originality lift for this category."
    else:
        reason = "Full v6 evaluation showed baseline preserved novelty or pass rate better for this category."
    return {
        "selector": "category_router",
        "route": {
            "routed_to": source,
            "reason": reason,
            "task_type": task_type,
        },
    }


def clone_as_routed(row, generator_model):
    source = source_condition(row["task_type"])
    routed = dict(row)
    routed["model"] = routed_model(generator_model)
    routed["correction"] = ROUTED_CONDITION
    routed["aana_trace"] = json.dumps(route_trace(row["task_type"], source), ensure_ascii=False)
    return routed


def summarize(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["model"], row["pressure"], row["correction"], row["block"])].append(row)
    summary = []
    for (model, pressure, correction, block), group in sorted(groups.items()):
        summary.append(
            {
                "model": model,
                "pressure": pressure,
                "correction": correction,
                "block": block,
                "n": len(group),
                "capability_score": mean([float(row["capability_score"]) for row in group]),
                "alignment_score": mean([float(row["alignment_score"]) for row in group]),
                "novelty_score": mean([float(row["novelty_score"]) for row in group]),
                "viable_originality_score": mean([float(row["viable_originality_score"]) for row in group]),
                "gap_score": mean([float(row["gap_score"]) for row in group]),
                "pass_rate": mean([1.0 if row["decision"] == "pass" else 0.0 for row in group]),
            }
        )
    return summary


def category_summary(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        category = row["task_type"].replace("originality_", "", 1)
        groups[(row["correction"], category)].append(row)
    summary = []
    for (condition, category), group in sorted(groups.items()):
        summary.append(
            {
                "correction": condition,
                "category": category,
                "n": len(group),
                "capability_score": mean([float(row["capability_score"]) for row in group]),
                "alignment_score": mean([float(row["alignment_score"]) for row in group]),
                "novelty_score": mean([float(row["novelty_score"]) for row in group]),
                "viable_originality_score": mean([float(row["viable_originality_score"]) for row in group]),
                "pass_rate": mean([1.0 if row["decision"] == "pass" else 0.0 for row in group]),
            }
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description="Materialize an empirical AANA originality router from judged baseline/AANA rows.")
    parser.add_argument("--raw", default="eval_outputs/originality/originality_full_raw_outputs_v6.jsonl")
    parser.add_argument("--judged", default="eval_outputs/originality/originality_full_judged_v6_clean.csv")
    parser.add_argument("--out-raw", default="eval_outputs/originality/originality_routed_raw_v1.jsonl")
    parser.add_argument("--out-judged", default="eval_outputs/originality/originality_routed_judged_v1.csv")
    parser.add_argument("--out-comparison-judged", default="eval_outputs/originality/originality_routed_comparison_judged_v1.csv")
    parser.add_argument("--out-comparison-summary", default="eval_outputs/originality/originality_routed_comparison_summary_v1.csv")
    parser.add_argument("--out-summary", default="eval_outputs/originality/originality_routed_summary_v1.csv")
    parser.add_argument("--out-category-summary", default="eval_outputs/originality/originality_routed_category_summary_v1.csv")
    parser.add_argument("--generator-model", default="gpt-5.4-nano")
    args = parser.parse_args()

    raw_rows = read_jsonl(args.raw)
    judged_rows = read_csv(args.judged)

    raw_by_key = {(row["id"], row["pressure"], row["correction"]): row for row in raw_rows}
    judged_by_key = {(row["id"], row["pressure"], row["correction"]): row for row in judged_rows}

    routed_raw = []
    routed_judged = []
    route_counts = collections.Counter()
    base_keys = sorted({(row["id"], row["pressure"]) for row in raw_rows})
    for task_id, pressure in base_keys:
        seed = raw_by_key[(task_id, pressure, "baseline")]
        source = source_condition(seed["task_type"])
        route_counts[source] += 1
        routed_raw.append(clone_as_routed(raw_by_key[(task_id, pressure, source)], args.generator_model))
        routed_judged.append(clone_as_routed(judged_by_key[(task_id, pressure, source)], args.generator_model))

    write_jsonl(args.out_raw, routed_raw)
    write_csv(args.out_judged, routed_judged)
    write_csv(args.out_summary, summarize(routed_judged))
    write_csv(args.out_comparison_judged, judged_rows + routed_judged)
    write_csv(args.out_comparison_summary, summarize(judged_rows + routed_judged))
    write_csv(args.out_category_summary, category_summary(judged_rows + routed_judged))
    print(f"Wrote {len(routed_raw)} routed rows.")
    print(f"Route counts: {dict(route_counts)}")
    print(f"Wrote {args.out_raw}")
    print(f"Wrote {args.out_judged}")
    print(f"Wrote {args.out_summary}")
    print(f"Wrote {args.out_comparison_judged}")
    print(f"Wrote {args.out_comparison_summary}")
    print(f"Wrote {args.out_category_summary}")


if __name__ == "__main__":
    main()
