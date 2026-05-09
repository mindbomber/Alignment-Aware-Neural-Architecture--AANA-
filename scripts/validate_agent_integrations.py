#!/usr/bin/env python
"""Validate the AANA agent integration stack end to end."""

from __future__ import annotations

import argparse
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
                "routes": routes,
                "blocked_write_executed": payload.get("blocked_write_executed"),
                "executed_tool_count": len(payload.get("executed_tool_calls") or []),
            }
        )
    except (json.JSONDecodeError, TypeError) as exc:
        check.update({"valid": False, "error": f"Could not parse wrapped-tools output: {exc}"})
    return check


def validate_fastapi_policy_service() -> dict[str, Any]:
    port = _free_port()
    token = "agent-integration-smoke-token"
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
        )
        return {
            "name": "fastapi_policy_service_smoke",
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
        }
    except Exception as exc:
        return {
            "name": "fastapi_policy_service_smoke",
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


def validate_controlled_agent_eval() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = run_controlled_agent_eval()
        metrics = result["metrics"]
        return {
            "name": "controlled_agent_eval_harness",
            "valid": bool(metrics.get("all_controlled_passed")),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "permissive_unsafe_executions": metrics.get("permissive_unsafe_executions"),
            "controlled_unsafe_executions": metrics.get("controlled_unsafe_executions"),
            "surfaces": metrics.get("surfaces"),
        }
    except Exception as exc:
        return {
            "name": "controlled_agent_eval_harness",
            "valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(exc),
        }


def validate_agent_integrations() -> dict[str, Any]:
    checks = [
        validate_openai_wrapped_tools(),
        validate_fastapi_policy_service(),
        validate_mcp_tool_smoke(),
        validate_controlled_agent_eval(),
    ]
    return {
        "valid": all(check.get("valid") for check in checks),
        "checks": checks,
        "passed": sum(1 for check in checks if check.get("valid")),
        "total": len(checks),
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
