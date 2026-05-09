#!/usr/bin/env python
"""Launch the AANA FastAPI service."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.fastapi_app import main


if __name__ == "__main__":
    raise SystemExit(main())

