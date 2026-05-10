#!/usr/bin/env python
"""Run the AANA single-node internal pilot service workflow."""

import argparse
import json
import os
import pathlib
import secrets
import subprocess
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import pilot_smoke_test
from eval_pipeline import agent_api


DEFAULT_MANIFEST = ROOT / "examples" / "production_deployment_internal_pilot.json"
DEFAULT_EVENT = ROOT / "examples" / "agent_event_support_reply.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_PORT = 8765
DEFAULT_PILOT_PHASE = "shadow_mode"


class PilotRunnerError(RuntimeError):
    pass


def load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def audit_log_from_manifest(manifest):
    sink = manifest.get("audit", {}).get("sink", "")
    if isinstance(sink, str) and sink.startswith("jsonl://"):
        return pathlib.Path(sink.removeprefix("jsonl://"))
    return ROOT / "eval_outputs" / "audit" / "aana-internal-pilot.jsonl"


def runtime_paths(manifest, audit_log_override=None):
    audit_log = pathlib.Path(audit_log_override) if audit_log_override else audit_log_from_manifest(manifest)
    audit_dir = audit_log.parent
    manifest_dir = audit_dir / "manifests"
    return {
        "audit_log": audit_log,
        "audit_dir": audit_dir,
        "integrity_manifest_dir": manifest_dir,
    }


def setup_runtime_directories(paths):
    created = []
    for key in ("audit_dir", "integrity_manifest_dir"):
        path = pathlib.Path(paths[key])
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(path))
    audit_log = pathlib.Path(paths["audit_log"])
    if not audit_log.exists():
        audit_log.touch()
        created.append(str(audit_log))
    return created


def audit_integrity_manifest_path(paths):
    audit_log = pathlib.Path(paths["audit_log"])
    manifest_dir = pathlib.Path(paths["integrity_manifest_dir"])
    return manifest_dir / f"{audit_log.stem}-integrity.json"


def audit_metrics_path(paths, metrics_output_override=None):
    if metrics_output_override:
        return pathlib.Path(metrics_output_override)
    audit_log = pathlib.Path(paths["audit_log"])
    return pathlib.Path(paths["audit_dir"]) / f"{audit_log.stem}-metrics.json"


def resolve_token(require_env_token=False):
    token = os.environ.get("AANA_BRIDGE_TOKEN")
    if token:
        return token, False
    if require_env_token:
        raise PilotRunnerError("AANA_BRIDGE_TOKEN is required but not set.")
    return secrets.token_urlsafe(32), True


def pilot_rollout(manifest):
    rollout = manifest.get("pilot_rollout", {})
    phases = sorted(rollout.get("phase_sequence", []), key=lambda item: item.get("order", 0))
    return {
        "default_phase": rollout.get("default_phase", DEFAULT_PILOT_PHASE),
        "autonomous_enforcement_allowed": bool(rollout.get("autonomous_enforcement_allowed", False)),
        "phases": phases,
    }


def pilot_phase(manifest, requested_phase=None):
    rollout = pilot_rollout(manifest)
    phase_name = requested_phase or rollout["default_phase"]
    for phase in rollout["phases"]:
        if phase.get("phase") == phase_name:
            return phase
    raise PilotRunnerError(f"Unknown pilot phase: {phase_name}")


def phase_shadow_mode_enabled(phase):
    return phase.get("mode") == "shadow" or phase.get("enforcement") == "observe_only"


def start_bridge(host, port, gallery, max_body_bytes, token, audit_log, shadow_mode=False):
    env = os.environ.copy()
    env["AANA_BRIDGE_TOKEN"] = token
    command = [
        sys.executable,
        str(ROOT / "scripts" / "aana_server.py"),
        "--host",
        host,
        "--port",
        str(port),
        "--gallery",
        str(gallery),
        "--max-body-bytes",
        str(max_body_bytes),
        "--audit-log",
        str(audit_log),
    ]
    if shadow_mode:
        command.append("--shadow-mode")
    return subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_bridge(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def collect_process_output(process):
    if process.stdout is None:
        return ""
    try:
        return process.stdout.read() or ""
    except OSError:
        return ""


def run_pilot(args):
    manifest = load_json(args.deployment_manifest)
    phase = pilot_phase(manifest, args.pilot_phase)
    shadow_mode = phase_shadow_mode_enabled(phase)
    bridge = manifest.get("bridge", {})
    host = args.host or bridge.get("host") or "127.0.0.1"
    port = args.port
    max_body_bytes = args.max_body_bytes or bridge.get("max_body_bytes") or 1_048_576
    paths = runtime_paths(manifest, args.audit_log)
    created = setup_runtime_directories(paths)
    token, generated_token = resolve_token(args.require_env_token)
    base_url = f"http://{host}:{port}"

    process = start_bridge(host, port, args.gallery, max_body_bytes, token, paths["audit_log"], shadow_mode=shadow_mode)
    try:
        try:
            pilot_smoke_test.wait_for_health(base_url, timeout_seconds=args.timeout)
        except Exception as exc:
            if process.poll() is not None:
                output = collect_process_output(process)
                raise PilotRunnerError(f"Bridge exited before health check passed. Output:\n{output}") from exc
            raise

        smoke_args = argparse.Namespace(
            base_url=base_url,
            host=host,
            port=port,
            token=token,
            require_env_token=True,
            event=args.event,
            gallery=args.gallery,
            deployment_manifest=args.deployment_manifest,
            audit_log=str(paths["audit_log"]),
            max_body_bytes=max_body_bytes,
            timeout=args.timeout,
            json=args.json,
            client_audit=False,
        )
        smoke = pilot_smoke_test.run_smoke_test(smoke_args)
        integrity_manifest = audit_integrity_manifest_path(paths)
        manifest = agent_api.create_audit_integrity_manifest(
            paths["audit_log"],
            manifest_path=integrity_manifest,
        )
        metrics_output = audit_metrics_path(paths, args.metrics_output)
        metrics = agent_api.export_audit_metrics_file(
            paths["audit_log"],
            output_path=metrics_output,
        )
        return {
            "status": "pass",
            "pilot_phase": {
                "phase": phase.get("phase"),
                "mode": phase.get("mode"),
                "enforcement": phase.get("enforcement"),
                "shadow_mode": shadow_mode,
                "autonomous_enforcement_allowed": pilot_rollout(manifest)["autonomous_enforcement_allowed"],
            },
            "base_url": base_url,
            "generated_process_token": generated_token,
            "runtime": {
                "audit_log": str(paths["audit_log"]),
                "audit_dir": str(paths["audit_dir"]),
                "integrity_manifest_dir": str(paths["integrity_manifest_dir"]),
                "integrity_manifest": str(integrity_manifest),
                "integrity_manifest_sha256": manifest["manifest_sha256"],
                "metrics": str(metrics_output),
                "metrics_version": metrics["audit_metrics_export_version"],
                "metrics_record_count": metrics["record_count"],
                "created": created,
            },
            "smoke_test": smoke,
        }
    finally:
        stop_bridge(process)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the AANA single-node internal pilot workflow.")
    parser.add_argument("--deployment-manifest", default=DEFAULT_MANIFEST, help="Internal pilot deployment manifest.")
    parser.add_argument("--event", default=DEFAULT_EVENT, help="Agent event used for the pilot smoke test.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery used by the bridge.")
    parser.add_argument("--host", default=None, help="Override bridge host from the deployment manifest.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bridge port for the pilot run.")
    parser.add_argument("--audit-log", default=None, help="Override the deployment manifest audit sink.")
    parser.add_argument("--metrics-output", default=None, help="Override the pilot audit metrics JSON output path.")
    parser.add_argument("--max-body-bytes", type=int, default=None, help="Override max POST body size.")
    parser.add_argument("--require-env-token", action="store_true", help="Require AANA_BRIDGE_TOKEN instead of generating a process-local token.")
    parser.add_argument("--timeout", type=float, default=10, help="Bridge health and HTTP timeout in seconds.")
    parser.add_argument("--pilot-phase", default=None, help="Pilot rollout phase. Defaults to the manifest default_phase.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_pilot(args)
    except (PilotRunnerError, pilot_smoke_test.SmokeTestError, OSError) as exc:
        print(f"AANA internal pilot runner: FAIL - {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("AANA internal pilot runner: PASS")
        print(
            "- Pilot phase: "
            f"{result['pilot_phase']['phase']} "
            f"mode={result['pilot_phase']['mode']} "
            f"enforcement={result['pilot_phase']['enforcement']}"
        )
        print(f"- Bridge: {result['base_url']}")
        print(f"- Generated process-local token: {result['generated_process_token']}")
        print(f"- Audit log: {result['runtime']['audit_log']}")
        print(f"- Runtime audit dir: {result['runtime']['audit_dir']}")
        print(f"- Runtime manifest dir: {result['runtime']['integrity_manifest_dir']}")
        print(f"- Audit integrity manifest: {result['runtime']['integrity_manifest']}")
        print(f"- Audit metrics: {result['runtime']['metrics']}")
        print(f"- Created runtime paths: {len(result['runtime']['created'])}")
        smoke = result["smoke_test"]
        print(
            "- Gate: "
            f"candidate={smoke['agent_check']['candidate_gate']} "
            f"final={smoke['agent_check']['gate_decision']} "
            f"action={smoke['agent_check']['recommended_action']}"
        )
        print(f"- Audit records: {smoke['audit']['summary']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
