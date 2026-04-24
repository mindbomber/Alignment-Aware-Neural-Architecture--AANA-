import argparse
import csv
import json
import pathlib

from common import DEFAULT_TASKS, read_jsonl
from run_evals import build_system_prompt, selected_prompt


def main():
    parser = argparse.ArgumentParser(
        description="Convert ATS/AANA tasks into OpenAI Batch API request JSONL."
    )
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    parser.add_argument("--output", default="eval_outputs/batch_requests.jsonl")
    parser.add_argument("--manifest", default="eval_outputs/batch_manifest.csv")
    parser.add_argument("--models", nargs="+", default=["gpt-5.4-nano"])
    parser.add_argument(
        "--pressures", nargs="+", choices=["low", "high"], default=["low", "high"]
    )
    parser.add_argument(
        "--corrections",
        nargs="+",
        choices=["baseline", "weak", "strong"],
        default=["baseline", "weak", "strong"],
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-output-tokens", type=int, default=450)
    args = parser.parse_args()

    tasks = read_jsonl(args.tasks)
    if args.limit is not None:
        tasks = tasks[: args.limit]

    output = pathlib.Path(args.output)
    manifest = pathlib.Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    count = 0
    with output.open("w", encoding="utf-8") as out:
        for task in tasks:
            for model in args.models:
                for pressure in args.pressures:
                    for correction in args.corrections:
                        custom_id = (
                            f"{task['id']}__{model}__{pressure}__{correction}"
                            .replace("/", "-")
                            .replace(":", "-")
                        )
                        request = {
                            "custom_id": custom_id,
                            "method": "POST",
                            "url": "/v1/responses",
                            "body": {
                                "model": model,
                                "input": [
                                    {
                                        "role": "system",
                                        "content": build_system_prompt(task, correction),
                                    },
                                    {
                                        "role": "user",
                                        "content": selected_prompt(task, pressure),
                                    },
                                ],
                                "max_output_tokens": args.max_output_tokens,
                            },
                        }
                        out.write(json.dumps(request, ensure_ascii=False) + "\n")
                        manifest_rows.append(
                            {
                                "custom_id": custom_id,
                                "id": task["id"],
                                "block": task["block"],
                                "task_type": task["task_type"],
                                "model": model,
                                "pressure": pressure,
                                "correction": correction,
                                "reference_notes": task["reference_notes"],
                            }
                        )
                        count += 1

    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Wrote {count} batch requests to {output}")
    print(f"Wrote manifest to {manifest}")


if __name__ == "__main__":
    main()
