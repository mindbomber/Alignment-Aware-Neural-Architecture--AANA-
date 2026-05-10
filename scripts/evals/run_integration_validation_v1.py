#!/usr/bin/env python
"""Run integration_validation_v1 held-out platform validation.

This experiment checks that AANA returns the same decision shape and execution
policy across CLI, SDK, FastAPI, MCP, and middleware surfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Callable


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aana  # noqa: E402
from eval_pipeline.mcp_server import call_tool  # noqa: E402


DEFAULT_CASES = ROOT / "examples" / "integration_validation_v1_heldout_cases.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "integration_validation_v1_heldout_results.json"
AUDIT_DIR = ROOT / "eval_outputs" / "audit"
REQUIRED_DECISION_KEYS = {
    "route",
    "aix_score",
    "hard_blockers",
    "missing_evidence",
    "authorization_state",
    "recovery_suggestion",
    "audit_event",
}
ROUTES = {"accept", "revise", "retrieve", "ask", "defer", "refuse"}


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


def _now_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _load_cases(path: pathlib.Path, *, case_limit: int | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if case_limit:
        payload = {**payload, "cases": cases[:case_limit]}
    if not payload.get("split_policy", {}).get("no_tuning_on_these_cases"):
        raise ValueError("integration validation cases must be marked no_tuning_on_these_cases=true")
    return payload


def _argument_keys(arguments: Any, prefix: str = "") -> list[str]:
    if isinstance(arguments, dict):
        keys: list[str] = []
        for key in sorted(arguments):
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.append(path)
            keys.extend(_argument_keys(arguments[key], path))
        return keys
    if isinstance(arguments, list):
        return [f"{prefix}[]"] if prefix else ["[]"]
    return []


def _architecture_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("architecture_decision"), dict):
        return payload["architecture_decision"]
    if isinstance(payload.get("structuredContent"), dict):
        return payload["structuredContent"]
    if isinstance(payload.get("result"), dict):
        return _architecture_decision(payload["result"])
    return payload


def _shape_errors(decision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_DECISION_KEYS - set(decision))
    if missing:
        errors.append(f"missing_decision_keys:{','.join(missing)}")
    if decision.get("route") not in ROUTES:
        errors.append("unsupported_route")
    if not isinstance(decision.get("aix_score"), int | float):
        errors.append("aix_score_not_numeric")
    if not isinstance(decision.get("hard_blockers"), list):
        errors.append("hard_blockers_not_list")
    if not isinstance(decision.get("missing_evidence"), list):
        errors.append("missing_evidence_not_list")
    if not isinstance(decision.get("authorization_state"), str):
        errors.append("authorization_state_not_string")
    audit_event = decision.get("audit_event")
    if not isinstance(audit_event, dict):
        errors.append("audit_event_missing")
    elif not {"route", "gate_decision", "aix_score", "hard_blockers", "raw_payload_logged"} <= set(audit_event):
        errors.append("audit_event_incomplete")
    return errors


def _schema_failed(payload: dict[str, Any]) -> bool:
    validation_errors = payload.get("validation_errors")
    if validation_errors:
        return True
    blockers = list(payload.get("hard_blockers") or [])
    architecture = _architecture_decision(payload)
    blockers.extend(architecture.get("hard_blockers") or [])
    return any("schema_validation_failed" in str(blocker) for blocker in blockers)


def _surface_record(
    *,
    surface: str,
    payload: dict[str, Any],
    latency_ms: float,
    tool_executed: bool | None = None,
    returncode: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    decision = _architecture_decision(payload if isinstance(payload, dict) else {})
    route = decision.get("route") or payload.get("route") or payload.get("recommended_action")
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    record = {
        "surface": surface,
        "route": route,
        "valid_shape": not _shape_errors(decision),
        "decision_shape_keys": sorted(decision),
        "decision_shape_errors": _shape_errors(decision),
        "audit_event_complete": "audit_event_incomplete" not in _shape_errors(decision) and "audit_event_missing" not in _shape_errors(decision),
        "schema_validation_failed": _schema_failed(payload),
        "execution_allowed": policy.get("execution_allowed"),
        "aana_allows_execution": policy.get("aana_allows_execution"),
        "tool_executed": tool_executed,
        "latency_ms": latency_ms,
    }
    if returncode is not None:
        record["returncode"] = returncode
    if error:
        record["error"] = error
    return record


def _post_json(url: str, payload: dict[str, Any], *, token: str, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_python_sdk(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    payload = aana.check_tool_call(case["event"])
    return _surface_record(surface="python_sdk", payload=payload, latency_ms=_now_ms(started))


def run_cli(case: dict[str, Any], *, audit_log: pathlib.Path) -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(case["event"], handle)
        event_path = pathlib.Path(handle.name)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/aana_cli.py",
                "pre-tool-check",
                "--event",
                str(event_path),
                "--audit-log",
                str(audit_log),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"architecture_decision": {"route": "refuse"}, "validation_errors": [{"path": "stdout", "message": "invalid_json"}]}
        return _surface_record(
            surface="cli",
            payload=payload,
            latency_ms=_now_ms(started),
            returncode=completed.returncode,
            error=completed.stderr.strip() or None,
        )
    finally:
        event_path.unlink(missing_ok=True)


def run_mcp(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    payload = call_tool("aana_pre_tool_check", case["event"])
    return _surface_record(surface="mcp_tool", payload=payload, latency_ms=_now_ms(started))


def _metadata_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_category": event["tool_category"],
        "authorization_state": event["authorization_state"],
        "risk_domain": event["risk_domain"],
        "evidence_refs": event.get("evidence_refs", []),
        "recommended_route": event.get("recommended_route", "accept"),
        "user_intent": event.get("user_intent"),
    }


def _wrapper_record(
    *,
    surface: str,
    case: dict[str, Any],
    wrapper_factory: Callable[[Callable[..., Any], dict[str, Any], Callable[[dict[str, Any]], None]], Any],
    invoke: Callable[[Any, dict[str, Any]], Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    calls: list[dict[str, Any]] = []
    gate_holder: dict[str, Any] = {}

    def tool(**kwargs: Any) -> dict[str, Any]:
        calls.append({"argument_keys": sorted(kwargs)})
        return {"executed": True}

    def on_decision(gate: dict[str, Any]) -> None:
        gate_holder["gate"] = gate

    try:
        wrapper = wrapper_factory(tool, _metadata_from_event(case["event"]), on_decision)
        result = invoke(wrapper, case["event"].get("proposed_arguments") or {})
        gate = gate_holder.get("gate") or getattr(wrapper, "aana_last_gate", None) or {}
        payload = gate.get("result") if isinstance(gate, dict) else {}
        if not isinstance(payload, dict) and isinstance(result, dict):
            payload = result.get("result") or result
        return _surface_record(surface=surface, payload=payload or {}, latency_ms=_now_ms(started), tool_executed=bool(calls))
    except Exception as exc:
        return _surface_record(
            surface=surface,
            payload=aana.fail_closed_tool_result(exc, case["event"]),
            latency_ms=_now_ms(started),
            tool_executed=bool(calls),
            error=str(exc),
        )


def run_python_wrapper(case: dict[str, Any]) -> dict[str, Any]:
    return _wrapper_record(
        surface="python_sdk_wrapper",
        case=case,
        wrapper_factory=lambda tool, metadata, on_decision: aana.wrap_agent_tool(
            tool,
            tool_name=case["event"]["tool_name"],
            metadata=metadata,
            on_decision=on_decision,
            raise_on_block=False,
        ),
        invoke=lambda wrapper, arguments: wrapper(**arguments),
    )


def run_openai_middleware(case: dict[str, Any]) -> dict[str, Any]:
    return _wrapper_record(
        surface="openai_agents_middleware",
        case=case,
        wrapper_factory=lambda tool, metadata, on_decision: aana.openai_agents_tool_middleware(
            tool,
            tool_name=case["event"]["tool_name"],
            metadata=metadata,
            on_decision=on_decision,
            raise_on_block=False,
        ),
        invoke=lambda wrapper, arguments: wrapper(**arguments),
    )


def run_autogen_middleware(case: dict[str, Any]) -> dict[str, Any]:
    return _wrapper_record(
        surface="autogen_middleware",
        case=case,
        wrapper_factory=lambda tool, metadata, on_decision: aana.autogen_tool_middleware(
            tool,
            tool_name=case["event"]["tool_name"],
            metadata=metadata,
            on_decision=on_decision,
            raise_on_block=False,
        ),
        invoke=lambda wrapper, arguments: wrapper(**arguments),
    )


def run_langchain_middleware(case: dict[str, Any]) -> dict[str, Any]:
    class Tool:
        name = case["event"]["tool_name"]

        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            self.calls += 1
            return {"executed": True, "argument_keys": sorted(payload)}

    started = time.perf_counter()
    gate_holder: dict[str, Any] = {}
    tool = Tool()

    def on_decision(gate: dict[str, Any]) -> None:
        gate_holder["gate"] = gate

    wrapper = aana.langchain_tool_middleware(
        tool,
        metadata=_metadata_from_event(case["event"]),
        on_decision=on_decision,
        raise_on_block=False,
    )
    wrapper.invoke(case["event"].get("proposed_arguments") or {})
    gate = gate_holder.get("gate") or getattr(wrapper, "aana_last_gate", {}) or {}
    return _surface_record(
        surface="langchain_middleware",
        payload=gate.get("result", {}),
        latency_ms=_now_ms(started),
        tool_executed=tool.calls > 0,
    )


def run_crewai_middleware(case: dict[str, Any]) -> dict[str, Any]:
    class Tool:
        name = case["event"]["tool_name"]

        def __init__(self) -> None:
            self.calls = 0

        def _run(self, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            return {"executed": True, "argument_keys": sorted(kwargs)}

    started = time.perf_counter()
    gate_holder: dict[str, Any] = {}
    tool = Tool()

    def on_decision(gate: dict[str, Any]) -> None:
        gate_holder["gate"] = gate

    wrapper = aana.crewai_tool_middleware(
        tool,
        metadata=_metadata_from_event(case["event"]),
        on_decision=on_decision,
        raise_on_block=False,
    )
    wrapper._run(**(case["event"].get("proposed_arguments") or {}))
    gate = gate_holder.get("gate") or getattr(wrapper, "aana_last_gate", {}) or {}
    return _surface_record(
        surface="crewai_middleware",
        payload=gate.get("result", {}),
        latency_ms=_now_ms(started),
        tool_executed=tool.calls > 0,
    )


def run_mcp_middleware(case: dict[str, Any]) -> dict[str, Any]:
    return _wrapper_record(
        surface="mcp_middleware",
        case=case,
        wrapper_factory=lambda tool, metadata, on_decision: aana.mcp_tool_middleware(
            lambda arguments=None, **kwargs: tool(**(arguments or kwargs or {})),
            tool_name=case["event"]["tool_name"],
            metadata=metadata,
            on_decision=on_decision,
            raise_on_block=False,
        ),
        invoke=lambda wrapper, arguments: wrapper(arguments),
    )


def run_typescript_sdk(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    script_path = ROOT / "eval_outputs" / "integration_validation_v1_typescript_runner.mjs"
    cases_path = ROOT / "eval_outputs" / "integration_validation_v1_typescript_cases.json"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(json.dumps(cases), encoding="utf-8")
    script_path.write_text(
        """
import fs from "node:fs";
import { checkToolCall, wrapAgentTool } from "../sdk/typescript/dist/index.js";

const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const output = {};
for (const item of cases) {
  const started = performance.now();
  const event = item.event;
  let gate = null;
  let calls = 0;
  const result = checkToolCall(event);
  const guarded = wrapAgentTool(
    event.tool_name,
    (_payload) => {
      calls += 1;
      return { executed: true };
    },
    {
      tool_category: event.tool_category,
      authorization_state: event.authorization_state,
      risk_domain: event.risk_domain,
      evidence_refs: event.evidence_refs,
      recommended_route: event.recommended_route,
      user_intent: event.user_intent
    },
    {
      raiseOnBlock: false,
      onDecision: (observed) => {
        gate = observed;
      }
    }
  );
  guarded(event.proposed_arguments ?? {});
  output[item.id] = {
    payload: result,
    wrapper_route: gate?.result?.architecture_decision?.route ?? null,
    tool_executed: calls > 0,
    latency_ms: Math.round((performance.now() - started) * 1000) / 1000
  };
}
console.log(JSON.stringify(output));
""".strip()
        + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(script_path), str(cases_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    payload = json.loads(completed.stdout)
    return {
        case_id: _surface_record(
            surface="typescript_sdk",
            payload=item["payload"],
            latency_ms=float(item["latency_ms"]),
            tool_executed=bool(item["tool_executed"]),
        )
        for case_id, item in payload.items()
    }


class FastAPIRunner:
    def __init__(self) -> None:
        self.port = _free_port()
        self.token = "redacted-integration-validation-v1-token"
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self.audit_log = AUDIT_DIR / "integration-validation-v1-fastapi.jsonl"
        self.stdout_path = AUDIT_DIR / "integration-validation-v1-fastapi.stdout.log"
        self.stderr_path = AUDIT_DIR / "integration-validation-v1-fastapi.stderr.log"
        self.stdout_handle = None
        self.stderr_handle = None
        self.proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> "FastAPIRunner":
        self.audit_log.unlink(missing_ok=True)
        self.stdout_handle = self.stdout_path.open("w", encoding="utf-8")
        self.stderr_handle = self.stderr_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/aana_fastapi.py",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--auth-token",
                self.token,
                "--audit-log",
                str(self.audit_log),
                "--rate-limit-per-minute",
                "0",
                "--max-request-bytes",
                "65536",
            ],
            cwd=ROOT,
            stdout=self.stdout_handle,
            stderr=self.stderr_handle,
            text=True,
        )
        for _ in range(60):
            if self.proc.poll() is not None:
                raise RuntimeError(f"FastAPI exited early with code {self.proc.returncode}.")
            try:
                health = _get_json(f"http://127.0.0.1:{self.port}/health", timeout=1.0)
                if health.get("status") == "ok":
                    return self
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        raise RuntimeError("FastAPI service did not become healthy.")

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.stdout_handle:
            self.stdout_handle.close()
        if self.stderr_handle:
            self.stderr_handle.close()

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        payload = _post_json(f"http://127.0.0.1:{self.port}/pre-tool-check", case["event"], token=self.token)
        return _surface_record(surface="fastapi", payload=payload, latency_ms=_now_ms(started))

    def audit_count(self) -> int:
        if not self.audit_log.exists():
            return 0
        return len([line for line in self.audit_log.read_text(encoding="utf-8").splitlines() if line.strip()])


def _safe_case_summary(case: dict[str, Any]) -> dict[str, Any]:
    event = case["event"]
    return {
        "id": case["id"],
        "source_dataset": case["source_dataset"],
        "source_schema": case["source_schema"],
        "split_role": case["split_role"],
        "tool_name": event["tool_name"],
        "tool_category": event["tool_category"],
        "authorization_state": event["authorization_state"],
        "risk_domain": event["risk_domain"],
        "argument_keys": _argument_keys(event.get("proposed_arguments") or {}),
        "argument_value_sha256": _sha256(event.get("proposed_arguments") or {}),
        "evidence_ref_count": len(event.get("evidence_refs") or []),
        "expected_route": case["expected_route"],
        "expected_blocked": bool(case["expected_blocked"]),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 3)


def _compute_metrics(rows: list[dict[str, Any]], *, fastapi_audit_records: int) -> dict[str, Any]:
    surface_records = [surface for row in rows for surface in row["surfaces"]]
    route_parity_count = sum(1 for row in rows if row["route_parity"])
    route_accuracy_count = sum(1 for row in rows if row["route_accuracy"])
    shape_valid_count = sum(1 for surface in surface_records if surface["valid_shape"])
    audit_complete_count = sum(1 for surface in surface_records if surface["audit_event_complete"])
    schema_failed_count = sum(1 for surface in surface_records if surface["schema_validation_failed"])
    wrapper_records = [surface for surface in surface_records if surface["tool_executed"] is not None]
    blocked_wrapper_records = [surface for row in rows for surface in row["surfaces"] if row["expected_blocked"] and surface["tool_executed"] is not None]
    blocked_non_execution = sum(1 for surface in blocked_wrapper_records if surface["tool_executed"] is False)
    latencies = [float(surface["latency_ms"]) for surface in surface_records if isinstance(surface.get("latency_ms"), int | float)]
    return {
        "case_count": len(rows),
        "surface_count": len(rows[0]["surfaces"]) if rows else 0,
        "surface_case_count": len(surface_records),
        "route_parity": round(route_parity_count / len(rows), 6) if rows else 0.0,
        "route_accuracy": round(route_accuracy_count / len(rows), 6) if rows else 0.0,
        "decision_shape_parity": round(shape_valid_count / len(surface_records), 6) if surface_records else 0.0,
        "audit_log_completeness": round(audit_complete_count / len(surface_records), 6) if surface_records else 0.0,
        "fastapi_audit_records": fastapi_audit_records,
        "fastapi_audit_coverage": round(fastapi_audit_records / len(rows), 6) if rows else 0.0,
        "schema_failure_rate": round(schema_failed_count / len(surface_records), 6) if surface_records else 0.0,
        "blocked_tool_non_execution": round(blocked_non_execution / len(blocked_wrapper_records), 6) if blocked_wrapper_records else 1.0,
        "wrapper_surface_count": len(wrapper_records),
        "latency_p50_ms": round(statistics.median(latencies), 3) if latencies else 0.0,
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_max_ms": round(max(latencies), 3) if latencies else 0.0,
    }


def run_experiment(cases_payload: dict[str, Any]) -> dict[str, Any]:
    cases = cases_payload["cases"]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    cli_audit_log = AUDIT_DIR / "integration-validation-v1-cli.jsonl"
    cli_audit_log.unlink(missing_ok=True)
    ts_results = run_typescript_sdk(cases)

    rows: list[dict[str, Any]] = []
    with FastAPIRunner() as fastapi:
        for case in cases:
            surfaces = [
                run_cli(case, audit_log=cli_audit_log),
                run_python_sdk(case),
                ts_results[case["id"]],
                fastapi.run_case(case),
                run_mcp(case),
                run_python_wrapper(case),
                run_openai_middleware(case),
                run_langchain_middleware(case),
                run_autogen_middleware(case),
                run_crewai_middleware(case),
                run_mcp_middleware(case),
            ]
            routes = [surface.get("route") for surface in surfaces]
            expected_route = case["expected_route"]
            rows.append(
                {
                    **_safe_case_summary(case),
                    "routes": {surface["surface"]: surface.get("route") for surface in surfaces},
                    "route_parity": len(set(routes)) == 1,
                    "route_accuracy": all(route == expected_route for route in routes),
                    "blocked_tool_non_execution": all(
                        surface["tool_executed"] is False
                        for surface in surfaces
                        if case["expected_blocked"] and surface["tool_executed"] is not None
                    ),
                    "surfaces": surfaces,
                    "raw_payload_logged": False,
                }
            )
        fastapi_audit_records = fastapi.audit_count()

    metrics = _compute_metrics(rows, fastapi_audit_records=fastapi_audit_records)
    return {
        "experiment_id": "integration_validation_v1_heldout",
        "result_label": "heldout",
        "claim_boundary": (
            "This validates AANA platform integration parity, audit-safe decision shape, "
            "and blocked-tool non-execution across local surfaces. It is not a raw "
            "agent-performance benchmark."
        ),
        "split_policy": cases_payload["split_policy"],
        "dataset_sources": [
            {
                "dataset_name": dataset_name,
                "schema_role": source_schema,
                "registry_allowed_use": split_role,
                "split_boundary": "Held-out platform validation only; do not tune on these cases.",
            }
            for dataset_name, source_schema, split_role in sorted(
                {
                    (case["source_dataset"], case["source_schema"], case["split_role"])
                    for case in cases
                }
            )
        ],
        "comparisons": [
            "cli",
            "python_sdk",
            "typescript_sdk",
            "fastapi",
            "mcp_tool",
            "python_sdk_wrapper",
            "openai_agents_middleware",
            "langchain_middleware",
            "autogen_middleware",
            "crewai_middleware",
            "mcp_middleware",
        ],
        "metrics": metrics,
        "rows": rows,
        "limitations": [
            "Held-out cases are small and focused on platform parity, not broad task success.",
            "HF-derived cases are redacted schema-style transformations, not full benchmark replay.",
            "Latency is local runtime latency and should not be treated as production deployment latency.",
            "No tuning was performed on these held-out integration cases.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=pathlib.Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-limit", type=int, default=None)
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases, case_limit=args.case_limit)
    result = run_experiment(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics = result["metrics"]
    status = "pass" if (
        metrics["route_parity"] == 1.0
        and metrics["route_accuracy"] == 1.0
        and metrics["decision_shape_parity"] == 1.0
        and metrics["blocked_tool_non_execution"] == 1.0
        and metrics["schema_failure_rate"] == 0.0
        and metrics["fastapi_audit_coverage"] >= 1.0
    ) else "block"
    print(
        f"{status} -- cases={metrics['case_count']} surfaces={metrics['surface_count']} "
        f"route_parity={metrics['route_parity']:.3f} route_accuracy={metrics['route_accuracy']:.3f} "
        f"blocked_tool_non_execution={metrics['blocked_tool_non_execution']:.3f} "
        f"audit_log_completeness={metrics['audit_log_completeness']:.3f} "
        f"schema_failure_rate={metrics['schema_failure_rate']:.3f} "
        f"latency_p95_ms={metrics['latency_p95_ms']:.3f} output={args.output}"
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
