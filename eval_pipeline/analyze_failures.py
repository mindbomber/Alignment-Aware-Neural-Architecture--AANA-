import argparse
import collections
import csv
import pathlib


CATEGORIES = {
    "incomplete_or_truncated": ["incomplete", "truncated", "ends mid", "unfinished", "cut off"],
    "budget_or_total": ["budget", "cost", "total", "$", "spend"],
    "time_accounting": ["time cap", "minutes", "hours", "weekday", "weekend", "saturday", "workday"],
    "dietary_exclusion": ["peanut", "dairy", "gluten", "vegetarian", "tree nut", "allergy"],
    "transport": ["rideshare", "taxi", "car", "transit"],
    "paid_item_cap": ["ticket", "attraction", "tour", "admission"],
    "creator_or_endorsement_ban": ["influencer", "creator", "endorsement", "sponsor"],
    "unsupported_specifics": ["unsupported", "assumption", "assumes", "verify", "available"],
}


def classify(rationale):
    text = (rationale or "").lower()
    labels = [
        name
        for name, needles in CATEGORIES.items()
        if any(needle in text for needle in needles)
    ]
    return labels or ["other"]


def main():
    parser = argparse.ArgumentParser(description="Categorize non-pass ATS/AANA judge rows.")
    parser.add_argument("--judged", default="eval_outputs/heldout/judged_outputs.csv")
    parser.add_argument("--output", default="eval_outputs/heldout/failure_analysis.csv")
    parser.add_argument("--block", default=None)
    parser.add_argument("--correction", default=None)
    args = parser.parse_args()

    with open(args.judged, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    failures = []
    counts = collections.Counter()
    for row in rows:
        if row.get("decision") == "pass":
            continue
        if args.block and row.get("block") != args.block:
            continue
        if args.correction and row.get("correction") != args.correction:
            continue
        labels = classify(row.get("rationale", ""))
        for label in labels:
            counts[(row.get("correction"), row.get("block"), label)] += 1
        failures.append(
            {
                "id": row.get("id"),
                "block": row.get("block"),
                "pressure": row.get("pressure"),
                "correction": row.get("correction"),
                "decision": row.get("decision"),
                "categories": ";".join(labels),
                "rationale": row.get("rationale"),
            }
        )

    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "block", "pressure", "correction", "decision", "categories", "rationale"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(failures)

    print(f"Wrote {len(failures)} failures to {output}")
    for (correction, block, label), count in sorted(counts.items()):
        print(f"{correction},{block},{label},{count}")


if __name__ == "__main__":
    main()
