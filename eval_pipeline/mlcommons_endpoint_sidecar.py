"""MLCommons endpoint sidecar contracts for AANA runtime governance."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
MLCOMMONS_ENDPOINT_SIDECAR_VERSION = "0.1"
MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_TYPE = "aana_mlcommons_endpoint_sidecar_contract"
DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_PATH = ROOT / "examples" / "mlcommons_endpoint_sidecar_contract.json"
DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_REPORT_PATH = ROOT / "eval_outputs" / "mlcommons_endpoints" / "sidecar-readiness-report.json"
CLAIM_BOUNDARY = (
    "AANA endpoint sidecar evidence is runtime governance evidence only; it is not MLCommons benchmark certification, "
    "production certification, or go-live approval for regulated industries."
)
FAIL_CLOSED_REQUIRED_RULE = {
    "gate_decision": "pass",
    "recommended_action": "accept",
    "hard_blockers": 0,
    "aix_hard_blockers": 0,
    "contract_errors": 0,
}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _section(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def endpoint_precheck_contract() -> dict[str, Any]:
    """Return the public endpoint precheck contract shape used by the sidecar."""

    return {
        "schema_version": "aana.mlcommons_endpoint_precheck.v1",
        "required_fields": [
            "run_id",
            "endpoint_id",
            "request_id",
            "benchmark",
            "model",
            "input_fingerprint",
            "candidate_output_fingerprint",
            "evidence_refs",
            "runtime_mode",
        ],
        "redaction_rule": "Store fingerprints, IDs, metrics, and governance metadata only; do not store raw prompts, raw completions, payloads, headers, credentials, PHI, PII, or benchmark sample text.",
        "example": {
            "schema_version": "aana.mlcommons_endpoint_precheck.v1",
            "run_id": "mlc-endpoint-run-2026-05-12",
            "endpoint_id": "sut-chat-endpoint",
            "request_id": "req-000001",
            "benchmark": {"suite": "mlcommons-endpoints", "scenario": "offline", "version": "0.1"},
            "model": {"model_id": "example-sut", "version": "2026-05-12"},
            "input_fingerprint": {"sha256": "redacted-input-sha256", "length": 2048},
            "candidate_output_fingerprint": {"sha256": "redacted-output-sha256", "length": 512},
            "evidence_refs": [{"source_id": "benchmark-run-config", "redaction_status": "redacted"}],
            "runtime_mode": "shadow",
            "policy_refs": ["endpoint_fail_closed_policy"],
            "metadata": {"sample_index": 1, "traffic_class": "benchmark"},
        },
    }


def default_endpoint_sidecar_contract() -> dict[str, Any]:
    """Return the default MLCommons endpoint sidecar integration contract."""

    return {
        "contract_type": MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_TYPE,
        "contract_version": MLCOMMONS_ENDPOINT_SIDECAR_VERSION,
        "surface": "mlcommons_endpoints",
        "product": "AANA Runtime + AANA AIx Audit",
        "claim_boundary": CLAIM_BOUNDARY,
        "pattern": {
            "name": "aana_sidecar_proxy",
            "runner_modification_required": False,
            "placement": "AANA sits beside or in front of the system-under-test endpoint and forwards allowed benchmark requests/responses.",
            "modes": ["observe", "shadow", "enforce"],
            "default_mode": "shadow",
        },
        "endpoint_precheck_contract": endpoint_precheck_contract(),
        "benchmark_run_metadata": {
            "required_fields": [
                "run_id",
                "benchmark_suite",
                "benchmark_version",
                "scenario",
                "sut_endpoint_id",
                "model_id",
                "started_at",
                "traffic_class",
            ],
            "optional_fields": ["hardware_profile", "region", "dataset_id", "operator", "git_sha", "runner_version"],
            "redacted_fields_only": True,
        },
        "impact_fields": {
            "latency": {
                "required": ["baseline_p50_ms", "baseline_p95_ms", "sidecar_p50_ms", "sidecar_p95_ms", "overhead_p95_ms"],
                "recommended": ["p99_ms", "timeout_count", "sidecar_timeout_count"],
            },
            "throughput": {
                "required": ["baseline_requests_per_second", "sidecar_requests_per_second", "throughput_delta_percent"],
                "recommended": ["tokens_per_second_baseline", "tokens_per_second_sidecar", "concurrency"],
            },
        },
        "fail_closed_policy": {
            "live_endpoint_deployment": True,
            "direct_forward_requires": dict(FAIL_CLOSED_REQUIRED_RULE),
            "bridge_unavailable": "block_or_defer",
            "contract_invalid": "block",
            "hard_blocker_present": "block",
            "shadow_mode": "log_would_block_without_blocking_benchmark",
        },
        "audit_logging": {
            "redacted_jsonl_required": True,
            "allowed_fields": [
                "run_id",
                "endpoint_id",
                "request_id",
                "gate_decision",
                "recommended_action",
                "aix_score",
                "aix_decision",
                "hard_blockers",
                "violation_codes",
                "latency_ms",
                "input_fingerprint",
                "output_fingerprint",
            ],
            "forbidden_fields": ["raw_prompt", "raw_output", "headers", "credentials", "phi", "pii", "sample_text"],
        },
    }


def load_endpoint_sidecar_contract(path: str | pathlib.Path = DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_PATH) -> dict[str, Any]:
    return _load_json(path)


def validate_endpoint_sidecar_contract(contract: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(contract, dict):
        return {
            "valid": False,
            "ready_for_shadow_benchmarking": False,
            "ready_for_live_endpoint_enforcement": False,
            "errors": 1,
            "warnings": 0,
            "issues": [_issue("error", "$", "Endpoint sidecar contract must be a JSON object.")],
        }
    if contract.get("contract_type") != MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_TYPE:
        issues.append(_issue("error", "contract_type", f"Must be {MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_TYPE}."))
    if contract.get("contract_version") != MLCOMMONS_ENDPOINT_SIDECAR_VERSION:
        issues.append(_issue("error", "contract_version", f"Must be {MLCOMMONS_ENDPOINT_SIDECAR_VERSION}."))
    if contract.get("surface") != "mlcommons_endpoints":
        issues.append(_issue("error", "surface", "Surface must be mlcommons_endpoints."))
    if "not mlcommons benchmark certification" not in str(contract.get("claim_boundary", "")).lower():
        issues.append(_issue("error", "claim_boundary", "Claim boundary must state this is not MLCommons benchmark certification."))

    pattern = _section(contract.get("pattern"))
    if pattern.get("runner_modification_required") is not False:
        issues.append(_issue("error", "pattern.runner_modification_required", "Sidecar pattern must not require MLCommons runner modification."))
    if pattern.get("default_mode") != "shadow":
        issues.append(_issue("error", "pattern.default_mode", "Default mode must be shadow for benchmark integration."))

    precheck = _section(contract.get("endpoint_precheck_contract"))
    required_precheck_fields = set(precheck.get("required_fields") or [])
    for field in endpoint_precheck_contract()["required_fields"]:
        if field not in required_precheck_fields:
            issues.append(_issue("error", "endpoint_precheck_contract.required_fields", f"Missing endpoint precheck field: {field}."))
    if "do not store raw prompts" not in str(precheck.get("redaction_rule", "")).lower():
        issues.append(_issue("error", "endpoint_precheck_contract.redaction_rule", "Redaction rule must prohibit raw prompt storage."))

    metadata = _section(contract.get("benchmark_run_metadata"))
    required_metadata = set(metadata.get("required_fields") or [])
    for field in ("run_id", "benchmark_suite", "scenario", "sut_endpoint_id", "model_id"):
        if field not in required_metadata:
            issues.append(_issue("error", "benchmark_run_metadata.required_fields", f"Missing benchmark metadata field: {field}."))
    if metadata.get("redacted_fields_only") is not True:
        issues.append(_issue("error", "benchmark_run_metadata.redacted_fields_only", "Benchmark metadata capture must be redacted-fields-only."))

    impact = _section(contract.get("impact_fields"))
    latency_required = set(_section(impact.get("latency")).get("required") or [])
    throughput_required = set(_section(impact.get("throughput")).get("required") or [])
    for field in ("baseline_p95_ms", "sidecar_p95_ms", "overhead_p95_ms"):
        if field not in latency_required:
            issues.append(_issue("error", "impact_fields.latency.required", f"Missing latency impact field: {field}."))
    for field in ("baseline_requests_per_second", "sidecar_requests_per_second", "throughput_delta_percent"):
        if field not in throughput_required:
            issues.append(_issue("error", "impact_fields.throughput.required", f"Missing throughput impact field: {field}."))

    policy = _section(contract.get("fail_closed_policy"))
    if policy.get("live_endpoint_deployment") is not True:
        issues.append(_issue("error", "fail_closed_policy.live_endpoint_deployment", "Live endpoint deployment must be fail-closed."))
    direct_rule = _section(policy.get("direct_forward_requires"))
    for key, expected in FAIL_CLOSED_REQUIRED_RULE.items():
        if direct_rule.get(key) != expected:
            issues.append(_issue("error", f"fail_closed_policy.direct_forward_requires.{key}", f"Direct forward requires {key}={expected!r}."))
    if policy.get("bridge_unavailable") not in {"block", "block_or_defer"}:
        issues.append(_issue("error", "fail_closed_policy.bridge_unavailable", "Bridge unavailable behavior must block or defer."))

    audit_logging = _section(contract.get("audit_logging"))
    if audit_logging.get("redacted_jsonl_required") is not True:
        issues.append(_issue("error", "audit_logging.redacted_jsonl_required", "Redacted JSONL audit logging is required."))
    forbidden = set(audit_logging.get("forbidden_fields") or [])
    for field in ("raw_prompt", "raw_output", "headers", "credentials"):
        if field not in forbidden:
            issues.append(_issue("error", "audit_logging.forbidden_fields", f"Forbidden audit field must be declared: {field}."))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "ready_for_shadow_benchmarking": errors == 0,
        "ready_for_live_endpoint_enforcement": False,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "summary": {
            "surface": contract.get("surface"),
            "default_mode": pattern.get("default_mode"),
            "runner_modification_required": pattern.get("runner_modification_required"),
        },
    }


def benchmark_run_metadata(
    *,
    run_id: str,
    benchmark_suite: str,
    benchmark_version: str,
    scenario: str,
    sut_endpoint_id: str,
    model_id: str,
    traffic_class: str = "benchmark",
    started_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create redacted benchmark run metadata for sidecar audit artifacts."""

    metadata = {
        "metadata_type": "aana_mlcommons_endpoint_benchmark_run_metadata",
        "metadata_version": MLCOMMONS_ENDPOINT_SIDECAR_VERSION,
        "run_id": run_id,
        "benchmark_suite": benchmark_suite,
        "benchmark_version": benchmark_version,
        "scenario": scenario,
        "sut_endpoint_id": sut_endpoint_id,
        "model_id": model_id,
        "traffic_class": traffic_class,
        "started_at": started_at or _utc_now(),
        "redacted_fields_only": True,
    }
    if extra:
        metadata["extra"] = dict(extra)
    return metadata


def sidecar_impact_report(
    *,
    run_metadata: dict[str, Any],
    baseline_p50_ms: float,
    baseline_p95_ms: float,
    sidecar_p50_ms: float,
    sidecar_p95_ms: float,
    baseline_requests_per_second: float,
    sidecar_requests_per_second: float,
) -> dict[str, Any]:
    """Build latency and throughput impact fields for endpoint benchmark reporting."""

    throughput_delta = 0.0
    if baseline_requests_per_second:
        throughput_delta = ((sidecar_requests_per_second - baseline_requests_per_second) / baseline_requests_per_second) * 100.0
    return {
        "report_type": "aana_mlcommons_endpoint_sidecar_impact",
        "report_version": MLCOMMONS_ENDPOINT_SIDECAR_VERSION,
        "run_metadata": run_metadata,
        "latency": {
            "baseline_p50_ms": round(float(baseline_p50_ms), 3),
            "baseline_p95_ms": round(float(baseline_p95_ms), 3),
            "sidecar_p50_ms": round(float(sidecar_p50_ms), 3),
            "sidecar_p95_ms": round(float(sidecar_p95_ms), 3),
            "overhead_p50_ms": round(float(sidecar_p50_ms) - float(baseline_p50_ms), 3),
            "overhead_p95_ms": round(float(sidecar_p95_ms) - float(baseline_p95_ms), 3),
        },
        "throughput": {
            "baseline_requests_per_second": round(float(baseline_requests_per_second), 3),
            "sidecar_requests_per_second": round(float(sidecar_requests_per_second), 3),
            "throughput_delta_percent": round(throughput_delta, 3),
        },
    }


def validate_sidecar_impact_report(report: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if report.get("report_type") != "aana_mlcommons_endpoint_sidecar_impact":
        issues.append(_issue("error", "report_type", "Invalid sidecar impact report type."))
    metadata = _section(report.get("run_metadata"))
    for field in ("run_id", "benchmark_suite", "scenario", "sut_endpoint_id", "model_id"):
        if not metadata.get(field):
            issues.append(_issue("error", f"run_metadata.{field}", "Benchmark run metadata field is required."))
    latency = _section(report.get("latency"))
    throughput = _section(report.get("throughput"))
    for field in ("baseline_p95_ms", "sidecar_p95_ms", "overhead_p95_ms"):
        if _number(latency.get(field)) is None:
            issues.append(_issue("error", f"latency.{field}", "Latency impact value must be numeric."))
    for field in ("baseline_requests_per_second", "sidecar_requests_per_second", "throughput_delta_percent"):
        if _number(throughput.get(field)) is None:
            issues.append(_issue("error", f"throughput.{field}", "Throughput impact value must be numeric."))
    if _number(latency.get("overhead_p95_ms")) is not None and latency["overhead_p95_ms"] < 0:
        issues.append(_issue("warning", "latency.overhead_p95_ms", "Negative p95 overhead should be verified against benchmark variance."))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def write_endpoint_sidecar_contract(
    path: str | pathlib.Path = DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_PATH,
) -> dict[str, Any]:
    contract = default_endpoint_sidecar_contract()
    validation = validate_endpoint_sidecar_contract(contract)
    _write_json(path, contract)
    return {"path": str(path), "contract": contract, "validation": validation}


def write_endpoint_sidecar_readiness_report(
    *,
    contract_path: str | pathlib.Path = DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_PATH,
    report_path: str | pathlib.Path = DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_REPORT_PATH,
) -> dict[str, Any]:
    contract = load_endpoint_sidecar_contract(contract_path)
    validation = validate_endpoint_sidecar_contract(contract)
    report = {
        "report_type": "aana_mlcommons_endpoint_sidecar_readiness",
        "report_version": MLCOMMONS_ENDPOINT_SIDECAR_VERSION,
        "created_at": _utc_now(),
        "contract_path": str(contract_path),
        "contract": contract,
        "validation": validation,
    }
    _write_json(report_path, report)
    return {"path": str(report_path), **report}


__all__ = [
    "CLAIM_BOUNDARY",
    "DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_PATH",
    "DEFAULT_MLCOMMONS_ENDPOINT_SIDECAR_REPORT_PATH",
    "FAIL_CLOSED_REQUIRED_RULE",
    "MLCOMMONS_ENDPOINT_SIDECAR_CONTRACT_TYPE",
    "MLCOMMONS_ENDPOINT_SIDECAR_VERSION",
    "benchmark_run_metadata",
    "default_endpoint_sidecar_contract",
    "endpoint_precheck_contract",
    "load_endpoint_sidecar_contract",
    "sidecar_impact_report",
    "validate_endpoint_sidecar_contract",
    "validate_sidecar_impact_report",
    "write_endpoint_sidecar_contract",
    "write_endpoint_sidecar_readiness_report",
]
