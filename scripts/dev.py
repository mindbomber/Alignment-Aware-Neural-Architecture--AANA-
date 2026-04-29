"""Small cross-platform helper commands for local development.

Usage:
    python scripts/dev.py test
    python scripts/dev.py sample
    python scripts/dev.py dry-run
    python scripts/dev.py check
"""

import argparse
import subprocess
import sys


PYTHON = sys.executable


def run(command):
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def compile_python():
    run([PYTHON, "-m", "compileall", "eval_pipeline", "tests", "scripts"])


def test():
    run([PYTHON, "-m", "unittest", "discover", "-s", "tests"])


def sample():
    run(
        [
            PYTHON,
            "eval_pipeline/score_outputs.py",
            "--input",
            "examples/sample_raw_outputs.jsonl",
            "--scored",
            "examples/sample_scored_outputs.csv",
            "--summary",
            "examples/sample_summary_by_condition.csv",
        ]
    )


def dry_run():
    run(
        [
            PYTHON,
            "eval_pipeline/generate_heldout_tasks.py",
            "--output",
            "eval_outputs/heldout/heldout_ats_aana_tasks.jsonl",
        ]
    )
    run(
        [
            PYTHON,
            "eval_pipeline/run_evals.py",
            "--limit",
            "2",
            "--dry-run",
            "--no-resume",
            "--output",
            "eval_outputs/raw_outputs.jsonl",
        ]
    )
    run(
        [
            PYTHON,
            "eval_pipeline/score_outputs.py",
            "--input",
            "eval_outputs/raw_outputs.jsonl",
            "--scored",
            "eval_outputs/scored_outputs.csv",
            "--summary",
            "eval_outputs/summary_by_condition.csv",
        ]
    )


def check():
    compile_python()
    test()
    sample()


COMMANDS = {
    "compile": compile_python,
    "test": test,
    "sample": sample,
    "dry-run": dry_run,
    "check": check,
}


def main():
    parser = argparse.ArgumentParser(description="Run common local development commands.")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
