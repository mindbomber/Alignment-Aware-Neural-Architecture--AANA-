#!/usr/bin/env python
"""Run the AANA pre-tool-call gate on a JSON event."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.pre_tool_call_gate import DEFAULT_SCHEMA, gate_pre_tool_call


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event", type=pathlib.Path, help="Path to an agent_tool_precheck event JSON file.")
    parser.add_argument("--schema", type=pathlib.Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    print(json.dumps(gate_pre_tool_call(event, args.schema), indent=2))


if __name__ == "__main__":
    main()
