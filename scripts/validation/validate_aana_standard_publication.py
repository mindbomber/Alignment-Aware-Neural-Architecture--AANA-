"""CLI wrapper for validating the AANA standard publication package."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.aana_standard_publication import main


if __name__ == "__main__":
    raise SystemExit(main())
