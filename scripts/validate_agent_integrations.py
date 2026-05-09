#!/usr/bin/env python
"""Validate the AANA agent integration stack end to end."""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.aana_controlled_agents.run_local import run_eval as run_controlled_agent_eval


REQUIRED_DECISION_SHAPE_KEYS = {
    "route",
    "aix_score",
    "hard_blockers",
    "missing_evidence",
    "authorization_state",
    "recovery_suggestion",
    "audit_event",
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_command(name: str, command: list[str], *, timeout: int = 120) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "name": name,
        "valid": completed.returncode == 0,
        "returncode": completed.returncode,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _parse_python_example_stdout(stdout: str) -> dict[str, Any]:
    return ast.literal_eval(stdout.strip())


def _decision_shape_errors(decision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_DECISION_SHAPE_KEYS - set(decision))
    if missing:
        errors.append(f"missing keys: {missing}")
    if decision.get("route") not in {"accept", "revise", "retrieve", "ask", "defer", "refuse"}:
        errors.append("route is not a supported AANA route")
    if not isinstance(decision.get("aix_score"), int | float):
        errors.append("aix_score must be numeric")
    if not isinstance(decision.get("hard_blockers"), list):
        errors.append("hard_blockers must be a list")
    if not isinstance(decision.get("missing_evidence"), list):
        errors.append("missing_evidence must be a list")
    if not isinstance(decision.get("authorization_state"), str):
        errors.append("authorization_state must be a string")
    if not isinstance(decision.get("recovery_suggestion"), str) or not decision.get("recovery_suggestion"):
        errors.append("recovery_suggestion must be a non-empty string")
    if not isinstance(decision.get("audit_event"), dict):
        errors.append("audit_event must be an object")
    return errors


def _architecture_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("architecture_decision"), dict):
        return payload["architecture_decision"]
    if isinstance(payload.get("structuredContent"), dict):
        return payload["structuredContent"]
    return payload


def _post_json(url: str, payload: dict[str, Any], *, token: str | None = None, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def validate_python_sdk() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        import aana

        accept = aana.check_tool_call(
            {
                "tool_name": "search_public_docs",
                "tool_category": "public_read",
                "authorization_state": "none",
                "evidence_refs": [{"source_id": "docs:index", "kind": "policy"}],
                "risk_domain": "public_information",
                "proposed_arguments": {"query": "Agent Action Contract"},
                "recommended_route": "accept",
            }
        )
        calls: list[dict[str, Any]] = []

        def send_email(to: str, body: str) -> dict[str, Any]:
            calls.append({"to": to, "body": body})
            return {"sent": True}

        guarded = aana.wrap_agent_tool(
            send_email,
            metadata={
                "tool_category": "write",
                "authorization_state": "validated",
                "risk_domain": "customer_support",
                "evidence_refs": [
                    {
                        "source_id": "policy.email.confirmation",
                        "kind": "policy",
                        "trust_tier": "verified",
                        "redaction_status": "redacted",
                        "summary": "Outbound customer email requires explicit user confirmation before sending.",
                    }
                ],
            },
            raise_on_block=False,
        )
        blocked = guarded(to="customer@example.com", body="Needs confirmation")
        blocked_result = blocked.get("result", {}) if isinstance(blocked, dict) else {}
        blocked_route = (
            blocked_result.get("route")
            or blocked_result.get("aana_route")
            or blocked_result.get("recommended_action")
        )
        shape_errors = _decision_shape_errors(_architecture_decision(accept))
        valid = accept.get("route") == "accept" and blocked_route == "ask" and calls == [] and not shape_errors
        return {
            "name": "python_sdk_smoke",
            "surface": "Python SDK",
            "valid": valid,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "accept_route": accept.get("route"),
            "blocked_route": blocked_route,
            "blocked_tool_executed": bool(calls),
            "decision_shape_keys": sorted(_architecture_decision(accept)),
            "decision_shape_errors": shape_errors,
        }
    except Exception as exc:
        return {
            "name": "python_sdk_smoke",
            "surface": "Python SDK",
            "valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(exc),
        }


def validate_typescript_sdk() -> dict[str, Any]:
    script = r"""
import { checkToolCall, wrapAgentTool } from "./sdk/typescript/dist/index.js";

const accept = checkToolCall({
  schema_version: "aana.agent_tool_precheck.v1",
  tool_name: "search_public_docs",
  tool_category: "public_read",
  authorization_state: "none",
  evidence_refs: [{ source_id: "docs:index", kind: "policy" }],
  risk_domain: "public_information",
  proposed_arguments: { query: "Agent Action Contract" },
  recommended_route: "accept"
});

let calls = 0;
const guarded = wrapAgentTool(
  "send_email",
  (_payload) => {
    calls += 1;
    return { sent: true };
  },
  {
    tool_category: "write",
    authorization_state: "validated",
    risk_domain: "customer_support",
    evidence_refs: [{
      source_id: "policy.email.confirmation",
      kind: "policy",
      trust_tier: "verified",
      redaction_status: "redacted",
      summary: "Outbound customer email requires explicit user confirmation before sending."
    }]
  },
  { raiseOnBlock: false }
);
const blocked = guarded({ to: "customer@example.com", body: "Needs confirmation" });
console.log(JSON.stringify({
  accept_route: accept.route ?? accept.aana_route ?? accept.recommended_action,
  blocked_route: blocked?.result?.route ?? blocked?.result?.aana_route ?? blocked?.result?.recommended_action,
  blocked_tool_executed: calls > 0,
  architecture_decision: accept.architecture_decision
}));
"""
    check = _run_command("typescript_sdk_smoke", ["node", "--input-type=module", "-e", script])
    check["surface"] = "TypeScript SDK"
    try:
        payload = json.loads(check["stdout"])
        valid = (
            check["valid"]
            and payload.get("accept_route") == "accept"
            and payload.get("blocked_route") == "ask"
            and payload.get("blocked_tool_executed") is False
            and not _decision_shape_errors(_architecture_decision(payload))
        )
        check.update(
            {
                "valid": valid,
                **payload,
                "decision_shape_keys": sorted(_architecture_decision(payload)),
                "decision_shape_errors": _decision_shape_errors(_architecture_decision(payload)),
            }
        )
    except (json.JSONDecodeError, TypeError) as exc:
        check.update({"valid": False, "error": f"Could not parse TypeScript SDK output: {exc}"})
    return check


def validate_cli_decision_shape() -> dict[str, Any]:
    check = _run_command(
        "cli_decision_shape_smoke",
        [
            sys.executable,
            "scripts/aana_cli.py",
            "pre-tool-check",
            "--event",
            "examples/api/pre_tool_check_confirmed_write.json",
        ],
    )
    check["surface"] = "CLI"
    try:
        payload = json.loads(check["stdout"])
        decision = _architecture_decision(payload)
        shape_errors = _decision_shape_errors(decision)
        valid = check["valid"] and payload.get("route") == "accept" and not shape_errors
        check.update(
            {
                "valid": valid,
                "route": payload.get("route"),
                "decision_shape_keys": sorted(decision),
                "decision_shape_errors": shape_errors,
            }
        )
    except (json.JSONDecodeError, TypeError) as exc:
        check.update({"valid": False, "error": f"Could not parse CLI output: {exc}"})
    return check


def validate_openai_wrapped_tools() -> dict[str, Any]:
    check = _run_command(
        "openai_wrapped_tools_smoke",
        [sys.executable, "examples/integrations/openai_agents/wrapped_tools.py"],
    )
    try:
        payload = json.loads(check["stdout"])
        routes = payload.get("routes", {})
        valid = (
            check["valid"]
            and routes.get("get_public_status") == "accept"
            and routes.get("get_customer_profile") == "accept"
            and routes.get("send_customer_email_without_confirmation") == "ask"
            and routes.get("send_customer_email_confirmed") == "accept"
            and payload.get("blocked_write_executed") is False
        )
        check.update(
            {
                "valid": valid,
                "surface": "OpenAI Agents SDK",
                "routes": routes,
                "blocked_write_executed": payload.get("blocked_write_executed"),
                "executed_tool_count": len(payload.get("executed_tool_calls") or []),
            }
        )
    except (json.JSONDecodeError, TypeError) as exc:
        check.update({"valid": False, "error": f"Could not parse wrapped-tools output: {exc}"})
    return check


def validate_framework_example(surface: str, filename: str) -> dict[str, Any]:
    check = _run_command(
        f"{surface.lower().replace(' ', '_')}_middleware_smoke",
        [sys.executable, f"examples/integrations/{filename}"],
    )
    check["surface"] = surface
    try:
        payload = _parse_python_example_stdout(check["stdout"])
        valid = (
            check["valid"]
            and payload.get("aana_route") == "accept"
            and isinstance(payload.get("tool_result"), dict)
        )
        check.update(
            {
                "valid": valid,
                "route": payload.get("aana_route"),
                "tool_result_keys": sorted(payload.get("tool_result", {}).keys())
                if isinstance(payload.get("tool_result"), dict)
                else [],
            }
        )
    except (SyntaxError, ValueError, TypeError) as exc:
        check.update({"valid": False, "error": f"Could not parse {surface} example output: {exc}"})
    return check


def validate_middleware_decision_shape() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        import aana

        calls: list[dict[str, Any]] = []

        def send_email(to: str, body: str) -> dict[str, Any]:
            calls.append({"to": to, "body": body})
            return {"sent": True}

        guarded = aana.openai_agents_tool_middleware(
            send_email,
            metadata={
                "tool_category": "write",
                "authorization_state": "validated",
                "risk_domain": "customer_support",
                "evidence_refs": [
                    {
                        "source_id": "policy.email.confirmation",
                        "kind": "policy",
                        "trust_tier": "verified",
                        "redaction_status": "redacted",
                        "summary": "Outbound customer email requires explicit user confirmation before sending.",
                    }
                ],
            },
            raise_on_block=False,
        )
        blocked = guarded(to="customer@example.com", body="Needs confirmation")
        gate = getattr(guarded, "aana_last_gate", {}) or {}
        decision = _architecture_decision((gate.get("result") or blocked or {}) if isinstance(gate, dict) else {})
        shape_errors = _decision_shape_errors(decision)
        return {
            "name": "middleware_decision_shape_smoke",
            "surface": "Middleware",
            "valid": decision.get("route") == "ask" and not calls and not shape_errors,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "route": decision.get("route"),
            "blocked_tool_executed": bool(calls),
            "decision_shape_keys": sorted(decision),
            "decision_shape_errors": shape_errors,
        }
    except Exception as exc:
        return {
            "name": "middleware_decision_shape_smoke",
            "surface": "Middleware",
            "valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(exc),
        }


def validate_fastapi_policy_service() -> dict[str, Any]:
    port = _free_port()
    token = "redacted-agent-integration-smoke-token"
    audit_log = ROOT / "eval_outputs" / "audit" / "agent-integrations-fastapi-smoke.jsonl"
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if audit_log.exists():
        audit_log.unlink()

    stdout_path = ROOT / "eval_outputs" / "audit" / "agent-integrations-fastapi.stdout.log"
    stderr_path = ROOT / "eval_outputs" / "audit" / "agent-integrations-fastapi.stderr.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "scripts/aana_fastapi.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--auth-token",
            token,
            "--audit-log",
            str(audit_log),
            "--rate-limit-per-minute",
            "0",
            "--max-request-bytes",
            "65536",
        ],
        cwd=ROOT,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    started = time.perf_counter()
    try:
        health = None
        for _ in range(60):
            if proc.poll() is not None:
                raise RuntimeError(f"FastAPI exited early with code {proc.returncode}.")
            try:
                health = _get_json(f"http://127.0.0.1:{port}/health", timeout=1.0)
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        if health is None:
            raise RuntimeError("FastAPI service did not become healthy.")

        ask_payload = json.loads((ROOT / "examples" / "api" / "pre_tool_check_write_ask.json").read_text(encoding="utf-8"))
        accept_payload = json.loads((ROOT / "examples" / "api" / "pre_tool_check_confirmed_write.json").read_text(encoding="utf-8"))
        ask = _post_json(f"http://127.0.0.1:{port}/pre-tool-check", ask_payload, token=token)
        accept = _post_json(f"http://127.0.0.1:{port}/pre-tool-check", accept_payload, token=token)
        audit_records = audit_log.read_text(encoding="utf-8").splitlines() if audit_log.exists() else []
        valid = (
            health.get("status") == "ok"
            and ask.get("route") == "ask"
            and ask.get("execution_policy", {}).get("execution_allowed") is False
            and accept.get("route") == "accept"
            and accept.get("execution_policy", {}).get("execution_allowed") is True
            and len(audit_records) >= 2
            and not _decision_shape_errors(_architecture_decision(accept))
        )
        return {
            "name": "fastapi_policy_service_smoke",
            "surface": "FastAPI",
            "valid": valid,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "port": port,
            "health_status": health.get("status"),
            "ask_route": ask.get("route"),
            "ask_execution_allowed": ask.get("execution_policy", {}).get("execution_allowed"),
            "accept_route": accept.get("route"),
            "accept_execution_allowed": accept.get("execution_policy", {}).get("execution_allowed"),
            "audit_records": len(audit_records),
            "audit_log_path": str(audit_log),
            "decision_shape_keys": sorted(_architecture_decision(accept)),
            "decision_shape_errors": _decision_shape_errors(_architecture_decision(accept)),
        }
    except Exception as exc:
        return {
            "name": "fastapi_policy_service_smoke",
            "surface": "FastAPI",
            "valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(exc),
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
        }
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        stdout_handle.close()
        stderr_handle.close()


def validate_mcp_tool_smoke() -> dict[str, Any]:
    check = _run_command("mcp_tool_smoke", [sys.executable, "scripts/aana_mcp_server.py", "--list-tools"])
    check["surface"] = "MCP descriptor"
    try:
        payload = json.loads(check["stdout"])
        tool = (payload.get("tools") or [{}])[0]
        valid = (
            check["valid"]
            and tool.get("name") == "aana_pre_tool_check"
            and tool.get("annotations", {}).get("readOnlyHint") is True
            and tool.get("annotations", {}).get("destructiveHint") is False
        )
        check.update(
            {
                "valid": valid,
                "tool_name": tool.get("name"),
                "read_only": tool.get("annotations", {}).get("readOnlyHint"),
                "destructive": tool.get("annotations", {}).get("destructiveHint"),
            }
        )
    except (json.JSONDecodeError, TypeError, IndexError) as exc:
        check.update({"valid": False, "error": f"Could not parse MCP smoke output: {exc}"})
    return check


def validate_mcp_decision_shape() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        from eval_pipeline.mcp_server import call_tool

        arguments = json.loads((ROOT / "examples/api/pre_tool_check_confirmed_write.json").read_text(encoding="utf-8"))
        payload = call_tool("aana_pre_tool_check", arguments)
        decision = _architecture_decision(payload)
        shape_errors = _decision_shape_errors(decision)
        return {
            "name": "mcp_decision_shape_smoke",
            "surface": "MCP decision shape",
            "valid": decision.get("route") == "accept" and not shape_errors,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "route": decision.get("route"),
            "decision_shape_keys": sorted(decision),
            "decision_shape_errors": shape_errors,
        }
    except Exception as exc:
        return {
            "name": "mcp_decision_shape_smoke",
            "surface": "MCP decision shape",
            "valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(exc),
        }


def validate_controlled_agent_eval() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = run_controlled_agent_eval()
        metrics = result["metrics"]
        return {
            "name": "controlled_agent_eval_harness",
            "surface": "Controlled agent eval",
            "valid": bool(metrics.get("all_controlled_passed")),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "permissive_unsafe_executions": metrics.get("permissive_unsafe_executions"),
            "controlled_unsafe_executions": metrics.get("controlled_unsafe_executions"),
            "surfaces": metrics.get("surfaces"),
        }
    except Exception as exc:
        return {
            "name": "controlled_agent_eval_harness",
            "surface": "Controlled agent eval",
            "valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(exc),
        }


def validate_agent_integrations() -> dict[str, Any]:
    checks = [
        validate_cli_decision_shape(),
        validate_python_sdk(),
        validate_typescript_sdk(),
        validate_openai_wrapped_tools(),
        validate_framework_example("LangChain", "langchain.py"),
        validate_framework_example("AutoGen", "autogen.py"),
        validate_framework_example("CrewAI", "crewai.py"),
        validate_middleware_decision_shape(),
        validate_fastapi_policy_service(),
        validate_mcp_tool_smoke(),
        validate_mcp_decision_shape(),
        validate_controlled_agent_eval(),
    ]
    return {
        "valid": all(check.get("valid") for check in checks),
        "checks": checks,
        "passed": sum(1 for check in checks if check.get("valid")),
        "total": len(checks),
        "surfaces": [check.get("surface") for check in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the full validation report as JSON.")
    args = parser.parse_args(argv)

    report = validate_agent_integrations()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- passed={report['passed']}/{report['total']}")
        for check in report["checks"]:
            check_status = "pass" if check.get("valid") else "block"
            print(f"- {check_status}: {check['name']}")
            if check.get("error"):
                print(f"  error: {check['error']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
