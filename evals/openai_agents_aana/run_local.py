"""Run the local OpenAI Agents + AANA guarded-tool eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aana
from evals.openai_agents_aana.graders import grade_case, summarize


HERE = Path(__file__).resolve().parent
CASES_PATH = HERE / "cases.jsonl"
RESULTS_DIR = HERE / "results"
LATEST_PATH = RESULTS_DIR / "latest.json"


class EvalLedger:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.calls.append({"tool_name": tool_name, "arguments": dict(arguments)})


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tool_registry(ledger: EvalLedger) -> dict[str, Callable[..., dict[str, Any]]]:
    def get_public_status(service: str) -> dict[str, Any]:
        ledger.record("get_public_status", {"service": service})
        return {"service": service, "status": "ok"}

    def get_customer_profile(customer_id: str) -> dict[str, Any]:
        ledger.record("get_customer_profile", {"customer_id": customer_id})
        return {"customer_id": customer_id, "profile": "redacted"}

    def send_customer_email(to: str, body: str) -> dict[str, Any]:
        ledger.record("send_customer_email", {"to": to, "body": body})
        return {"sent": True, "to": to}

    def sync_external_record(record_id: str) -> dict[str, Any]:
        ledger.record("sync_external_record", {"record_id": record_id})
        return {"synced": True}

    return {
        "get_public_status": get_public_status,
        "get_customer_profile": get_customer_profile,
        "send_customer_email": send_customer_email,
        "sync_external_record": sync_external_record,
    }


def run_aana_case(case: dict[str, Any]) -> dict[str, Any]:
    ledger = EvalLedger()
    tools = tool_registry(ledger)
    output = aana.execute_tool_if_allowed(
        tools[case["tool_name"]],
        tool_name=case["tool_name"],
        arguments=dict(case["proposed_arguments"]),
        metadata={
            "tool_category": case["tool_category"],
            "authorization_state": case["authorization_state"],
            "risk_domain": case["risk_domain"],
        },
        evidence_refs=list(case.get("evidence_refs") or []),
        raise_on_block=False,
    )
    return {
        "aana": output["aana"],
        "gate": {
            "execution_allowed": output["gate"]["execution_allowed"],
            "execution_policy": output["gate"]["execution_policy"],
        },
        "tool_result": output["tool_result"],
        "ledger": ledger.calls,
    }


def run_permissive_case(case: dict[str, Any]) -> dict[str, Any]:
    ledger = EvalLedger()
    tools = tool_registry(ledger)
    result = tools[case["tool_name"]](**dict(case["proposed_arguments"]))
    return {"tool_result": result, "ledger": ledger.calls}


def run_eval(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases or load_cases()
    case_results = []
    rows = []
    for case in cases:
        aana_output = run_aana_case(case)
        permissive_output = run_permissive_case(case)
        grade = grade_case(case, aana_output, permissive_output)
        case_results.append(grade)
        rows.append(
            {
                "case": case,
                "aana_output": aana_output,
                "permissive_output": permissive_output,
                "grade": grade,
            }
        )

    metrics = summarize(case_results)
    result = {
        "eval_name": "openai_agents_aana_guarded_tool_eval",
        "description": "Local OpenAI-style agent tool-call eval for AANA middleware and API guard behavior.",
        "metrics": metrics,
        "rows": rows,
    }
    return result


def main() -> int:
    result = run_eval()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2, sort_keys=True))
    return 0 if result["metrics"]["passed"] == result["metrics"]["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
