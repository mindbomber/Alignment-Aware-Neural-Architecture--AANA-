#!/usr/bin/env python
"""Launch the local AANA HTTP bridge with everyday action demos enabled."""

import argparse
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_server


def build_parser():
    parser = argparse.ArgumentParser(description="Run the AANA local desktop/browser demos.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    parser.add_argument("--gallery", default=str(ROOT / "examples" / "adapter_gallery.json"), help="Adapter gallery JSON path.")
    parser.add_argument("--auth-token", default=None, help="POST auth token. Defaults to AANA_BRIDGE_TOKEN or a local demo token.")
    parser.add_argument(
        "--audit-log",
        default=str(ROOT / "eval_outputs" / "audit" / "demos" / "aana-local-demos.jsonl"),
        help="Path for redacted local demo audit JSONL records.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    audit_log = pathlib.Path(args.audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    token = args.auth_token or os.environ.get(agent_server.DEFAULT_TOKEN_ENV) or "aana-local-dev-token"
    print(f"AANA local action demos: http://{args.host}:{args.port}/demos")
    print(f"AANA adapter playground: http://{args.host}:{args.port}/playground")
    agent_server.run_server(
        host=args.host,
        port=args.port,
        gallery_path=args.gallery,
        auth_token=token,
        audit_log_path=audit_log,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
