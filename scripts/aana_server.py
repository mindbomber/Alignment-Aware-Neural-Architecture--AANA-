#!/usr/bin/env python
"""Launch the local AANA agent HTTP bridge."""

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.agent_server import main


if __name__ == "__main__":
    raise SystemExit(main())
