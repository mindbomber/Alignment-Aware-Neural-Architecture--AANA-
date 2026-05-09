"""Run AANA-controlled agent eval harnesses across SDK, API, and MCP surfaces."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aana
from eval_pipeline import mcp_server
from eval_pipeline.fastapi_app import create_app
from evals.aana_controlled_agents.graders import grade_surface, summarize
from fastapi.testclient import TestClient


HERE = Path(__file__).resolve().parent
CASES_PATH = HERE / "cases.jsonl"
RESULTS_DIR = HERE / "results"
LATEST_PATH = RESULTS_DIR / "latest.json"


class ToolLedger:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.calls.append({"tool_name": tool_name, "arguments": dict(arguments)})


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tool_registry(ledger: ToolLedger) -> dict[str, Callable[..., dict[str, Any]]]:
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

    def deploy_service(service: str, environment: str) -> dict[str, Any]:
        ledger.record("deploy_service", {"service": service, "environment": environment})
        return {"deployed": True, "service": service, "environment": environment}

    return {
        "get_public_status": get_public_status,
        "get_customer_profile": get_customer_profile,
        "send_customer_email": send_customer_email,
        "sync_external_record": sync_external_record,
        "deploy_service": deploy_service,
    }


def event_from_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_name": case["tool_name"],
        "tool_category": case["tool_category"],
        "authorization_state": case["authorization_state"],
        "evidence_refs": list(case.get("evidence_refs") or []),
        "risk_domain": case["risk_domain"],
        "proposed_arguments": dict(case["proposed_arguments"]),
        "recommended_route": case.get("recommended_route", "accept"),
    }


def execute_tool(case: dict[str, Any], ledger: ToolLedger) -> dict[str, Any]:
    tool = tool_registry(ledger)[case["tool_name"]]
    return tool(**dict(case["proposed_arguments"]))


def run_permissive(case: dict[str, Any]) -> dict[str, Any]:
    ledger = ToolLedger()
    result = execute_tool(case, ledger)
    return {"surface": "permissive", "executed": True, "tool_result": result, "ledger": ledger.calls}


def run_sdk(case: dict[str, Any]) -> dict[str, Any]:
    ledger = ToolLedger()
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
        "surface": "sdk",
        "decision": output["aana"],
        "executed": output["tool_result"] is not None,
        "tool_result": output["tool_result"],
        "ledger": ledger.calls,
    }


def run_api(case: dict[str, Any], client: TestClient) -> dict[str, Any]:
    ledger = ToolLedger()
    response = client.post("/pre-tool-check", json=event_from_case(case), headers={"Authorization": "Bearer eval-token"})
    response.raise_for_status()
    decision = response.json()
    policy = decision.get("execution_policy") if isinstance(decision.get("execution_policy"), dict) else {}
    executed = bool(policy.get("execution_allowed"))
    tool_result = execute_tool(case, ledger) if executed else None
    return {
        "surface": "api",
        "decision": decision,
        "executed": executed,
        "tool_result": tool_result,
        "ledger": ledger.calls,
    }


def run_mcp(case: dict[str, Any]) -> dict[str, Any]:
    ledger = ToolLedger()
    response = mcp_server.handle_aana_pre_tool_check(event_from_case(case))
    decision = response["structuredContent"]
    executed = bool(decision.get("execution_allowed"))
    tool_result = execute_tool(case, ledger) if executed else None
    return {
        "surface": "mcp",
        "decision": decision,
        "executed": executed,
        "tool_result": tool_result,
        "ledger": ledger.calls,
        "mcp_response": response,
    }


def run_eval(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases or load_cases()
    api_client = TestClient(create_app(auth_token="eval-token", rate_limit_per_minute=0, max_request_bytes=0))
    rows = []
    grades = []
    for case in cases:
        outputs = [
            run_permissive(case),
            run_sdk(case),
            run_api(case, api_client),
            run_mcp(case),
        ]
        row_grades = [grade_surface(case, output["surface"], output) for output in outputs]
        grades.extend(row_grades)
        rows.append({"case": case, "outputs": outputs, "grades": row_grades})

    metrics = summarize(grades)
    return {
        "eval_name": "aana_controlled_agents_multisurface_eval",
        "description": "AANA-controlled agent harness across permissive, SDK, FastAPI, and MCP execution surfaces.",
        "metrics": metrics,
        "rows": rows,
    }


def main() -> int:
    result = run_eval()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2, sort_keys=True))
    return 0 if result["metrics"]["all_controlled_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
