#!/usr/bin/env python
"""Compatibility wrapper for the AANA platform validator."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aana.validate_platform import main


if __name__ == "__main__":
    raise SystemExit(main())
