"""AANA integration helpers for Accenture MCP-Bench.

The wrapper is intentionally an overlay: it does not fork MCP-Bench and it does
not alter the benchmark task files. It patches MCP-Bench's real tool execution
boundary, `PersistentMultiServerManager.call_tool`, so the same base agent can
run once plain and once with AANA enforcing the pre-tool-call contract.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from aana.sdk import execution_policy
from eval_pipeline.agent_tool_use_control import convert_tool_call_to_precheck_event, infer_risk_domain, infer_tool_category
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call_v2, validate_event


DEFAULT_MODEL_PATH = "__mcp_bench_no_tau2_model__.joblib"
UTILITY_PUBLIC_HINTS = (
    "api",
    "calculate",
    "calculator",
    "check",
    "convert",
    "current",
    "docs",
    "estimate",
    "fetch",
    "find",
    "forecast",
    "get",
    "list",
    "lookup",
    "metric",
    "overview",
    "read",
    "recommend",
    "search",
    "summarize",
    "time",
    "unit",
    "weather",
)
CONSEQUENTIAL_HINTS = (
    "add",
    "approve",
    "book",
    "buy",
    "cancel",
    "create",
    "delete",
    "deploy",
    "edit",
    "execute",
    "grant",
    "kill",
    "modify",
    "move",
    "pay",
    "post",
    "purchase",
    "refund",
    "remove",
    "restart",
    "revoke",
    "send",
    "submit",
    "terminate",
    "transfer",
    "update",
    "write",
)


@dataclass(slots=True)
class MCPBenchAANAConfig:
    """Runtime settings for the MCP-Bench AANA wrapper."""

    execution_mode: str = "enforce"
    authorization_state: str = "confirmed"
    risk_domain: str = "agent_tool_use"
    audit_log_path: pathlib.Path | None = None
    model_path: str = DEFAULT_MODEL_PATH
    condition_name: str = "base_agent_plus_aana"
    fail_closed_on_schema_error: bool = True


class _TextContent:
    def __init__(self, text: str):
        self.text = text


class AANABlockedToolResult:
    """Minimal MCP result shape consumed by MCP-Bench's result extractor."""

    isError = True

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.content = [_TextContent(json.dumps(payload, sort_keys=True))]

    def __str__(self) -> str:
        return json.dumps(self.payload, sort_keys=True)


def _sha256(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        encoded = str(value)
    return hashlib.sha256(encoded.encode("utf-8", errors="replace")).hexdigest()


def _argument_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "argument_keys": sorted(str(key) for key in arguments.keys()),
        "argument_count": len(arguments),
        "argument_sha256": _sha256(arguments),
    }


def infer_mcp_bench_tool_category(tool_name: str, arguments: dict[str, Any], description: str) -> str:
    """Infer a benchmark tool category without using benchmark labels."""

    category = infer_tool_category(tool_name, arguments, description)
    if category in {"public_read", "private_read"}:
        return category
    tool_surface = f"{tool_name} {description}".lower()
    if any(hint in tool_surface for hint in CONSEQUENTIAL_HINTS):
        return "write"
    if any(hint in tool_surface for hint in UTILITY_PUBLIC_HINTS):
        return "public_read"
    if category == "write":
        return category
    text = f"{tool_surface} {json.dumps(arguments, sort_keys=True, default=str)}".lower()
    if any(hint in text for hint in CONSEQUENTIAL_HINTS):
        return "write"
    return "unknown"


def build_mcp_bench_precheck_event(
    *,
    tool_name: str,
    parameters: dict[str, Any] | None,
    tool_info: dict[str, Any] | None,
    task_context: str | None,
    config: MCPBenchAANAConfig,
) -> dict[str, Any]:
    """Convert an MCP-Bench tool call into Agent Action Contract v1."""

    info = tool_info or {}
    args = dict(parameters or {})
    server = str(info.get("server") or "unknown_server")
    original_name = str(info.get("original_name") or info.get("name") or tool_name)
    description = str(info.get("description") or "")
    category = infer_mcp_bench_tool_category(tool_name, args, description)
    source_domain = f"mcp_bench {server} {config.risk_domain}"
    row = {
        "id": f"mcp-bench-{_sha256({'tool': tool_name, 'args': args})[:16]}",
        "source_dataset": "Accenture/mcp-bench",
        "source_family": "mcp_bench",
        "source_schema": "runtime_tool_call",
        "source_domain": source_domain,
        "tool_name": tool_name,
        "tool_description": description,
        "tool_category": category,
        "authorization_state": config.authorization_state,
        "risk_domain": infer_risk_domain(source_domain, original_name, args),
        "proposed_arguments": args,
        "recommended_route": "accept",
        "user_intent": str(task_context or "MCP-Bench runtime proposed this MCP tool call.")[:500],
        "trace_features": {
            "has_user_request": True,
            "has_prior_auth_lookup": config.authorization_state in {"authenticated", "validated", "confirmed"},
            "has_prior_validation_tool": config.authorization_state in {"validated", "confirmed"},
            "has_explicit_confirmation": config.authorization_state == "confirmed",
        },
    }
    event = convert_tool_call_to_precheck_event(row)
    event["tool_name"] = tool_name
    return event


def _decision_route(result: dict[str, Any]) -> str:
    architecture = result.get("architecture_decision") if isinstance(result.get("architecture_decision"), dict) else {}
    return str(architecture.get("route") or result.get("recommended_action") or "refuse")


def _blocked_payload(event: dict[str, Any], result: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    architecture = result.get("architecture_decision") if isinstance(result.get("architecture_decision"), dict) else {}
    return {
        "aana_blocked": True,
        "route": _decision_route(result),
        "tool_name": event.get("tool_name"),
        "tool_category": event.get("tool_category"),
        "risk_domain": event.get("risk_domain"),
        "hard_blockers": list(dict.fromkeys((result.get("hard_blockers") or []) + (architecture.get("hard_blockers") or []))),
        "missing_evidence": architecture.get("missing_evidence") or [],
        "authorization_state": event.get("authorization_state"),
        "recovery_suggestion": architecture.get("correction_recovery_suggestion")
        or "Retry only after AANA receives enough evidence and authorization to return accept.",
        "execution_policy": {
            "mode": policy.get("mode"),
            "reason": policy.get("reason"),
            "required_route": policy.get("required_route"),
        },
    }


def _audit_record(
    *,
    condition: str,
    event: dict[str, Any],
    result: dict[str, Any],
    policy: dict[str, Any],
    arguments: dict[str, Any],
    latency_ms: float,
) -> dict[str, Any]:
    architecture = result.get("architecture_decision") if isinstance(result.get("architecture_decision"), dict) else {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark": "mcp-bench",
        "condition": condition,
        "request_id": event.get("request_id"),
        "tool_name": event.get("tool_name"),
        "tool_category": event.get("tool_category"),
        "risk_domain": event.get("risk_domain"),
        "authorization_state": event.get("authorization_state"),
        "route": _decision_route(result),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "execution_allowed": policy.get("execution_allowed"),
        "aana_allows_execution": policy.get("aana_allows_execution"),
        "hard_blockers": list(dict.fromkeys((result.get("hard_blockers") or []) + (architecture.get("hard_blockers") or []))),
        "missing_evidence": architecture.get("missing_evidence") or [],
        "policy_reason": policy.get("reason"),
        "latency_ms": round(latency_ms, 3),
        **_argument_summary(arguments),
    }


def _append_jsonl(path: pathlib.Path | None, record: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def make_aana_guarded_manager_class(base_manager_cls: type, config: MCPBenchAANAConfig) -> type:
    """Return a guarded subclass of MCP-Bench's PersistentMultiServerManager."""

    class AANAGuardedPersistentMultiServerManager(base_manager_cls):  # type: ignore[misc, valid-type]
        aana_config = config

        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, **kwargs)
            self.aana_task_context: str | None = None
            self.aana_decisions: list[dict[str, Any]] = []

        def set_aana_task_context(self, task: str | None) -> None:
            self.aana_task_context = task

        async def call_tool(self, tool_name: str, parameters: dict[str, Any], use_cache: bool = True) -> Any:
            started = time.perf_counter()
            args = dict(parameters or {})
            tool_info = self.all_tools.get(tool_name, {}) if isinstance(getattr(self, "all_tools", None), dict) else {}
            try:
                event = build_mcp_bench_precheck_event(
                    tool_name=tool_name,
                    parameters=args,
                    tool_info=tool_info,
                    task_context=self.aana_task_context,
                    config=self.aana_config,
                )
                validate_event(event)
                result = gate_pre_tool_call_v2(event, model_path=self.aana_config.model_path)
            except Exception as exc:
                if not self.aana_config.fail_closed_on_schema_error:
                    return await super().call_tool(tool_name, parameters, use_cache=use_cache)
                event = {
                    "request_id": f"mcp-bench-schema-error-{_sha256({'tool': tool_name, 'args': args})[:16]}",
                    "tool_name": tool_name,
                    "tool_category": "unknown",
                    "authorization_state": "none",
                    "risk_domain": self.aana_config.risk_domain,
                    "proposed_arguments": args,
                    "recommended_route": "refuse",
                }
                result = {
                    "gate_decision": "fail",
                    "recommended_action": "refuse",
                    "hard_blockers": ["mcp_bench_contract_normalization_failed"],
                    "validation_errors": [{"path": "event", "message": str(exc)}],
                    "architecture_decision": {
                        "route": "refuse",
                        "hard_blockers": ["mcp_bench_contract_normalization_failed"],
                        "correction_recovery_suggestion": "Fix the MCP tool-call contract before execution.",
                    },
                }
            policy = execution_policy(result, mode=self.aana_config.execution_mode)
            latency_ms = (time.perf_counter() - started) * 1000
            audit = _audit_record(
                condition=self.aana_config.condition_name,
                event=event,
                result=result,
                policy=policy,
                arguments=args,
                latency_ms=latency_ms,
            )
            self.aana_decisions.append(audit)
            _append_jsonl(self.aana_config.audit_log_path, audit)
            if policy["execution_allowed"]:
                return await super().call_tool(tool_name, parameters, use_cache=use_cache)
            return AANABlockedToolResult(_blocked_payload(event, result, policy))

    AANAGuardedPersistentMultiServerManager.__name__ = "AANAGuardedPersistentMultiServerManager"
    return AANAGuardedPersistentMultiServerManager


def make_aana_task_executor_class(base_executor_cls: type) -> type:
    """Return a TaskExecutor subclass that shares task context with the gate."""

    class AANATaskExecutor(base_executor_cls):  # type: ignore[misc, valid-type]
        async def execute(self, task: str) -> dict[str, Any]:
            setter: Callable[[str], None] | None = getattr(self.server_manager, "set_aana_task_context", None)
            if setter:
                setter(task)
            return await super().execute(task)

    AANATaskExecutor.__name__ = "AANATaskExecutor"
    return AANATaskExecutor


def install_mcp_bench_aana_guard(runner_module: Any, config: MCPBenchAANAConfig) -> dict[str, Any]:
    """Patch an imported MCP-Bench `benchmark.runner` module in place.

    Returns the original classes so callers can restore them if needed.
    """

    original_manager = runner_module.PersistentMultiServerManager
    original_executor = runner_module.TaskExecutor
    runner_module.PersistentMultiServerManager = make_aana_guarded_manager_class(original_manager, config)
    runner_module.TaskExecutor = make_aana_task_executor_class(original_executor)
    return {
        "PersistentMultiServerManager": original_manager,
        "TaskExecutor": original_executor,
    }


def restore_mcp_bench_aana_guard(runner_module: Any, originals: dict[str, Any]) -> None:
    """Restore MCP-Bench classes replaced by `install_mcp_bench_aana_guard`."""

    if "PersistentMultiServerManager" in originals:
        runner_module.PersistentMultiServerManager = originals["PersistentMultiServerManager"]
    if "TaskExecutor" in originals:
        runner_module.TaskExecutor = originals["TaskExecutor"]
