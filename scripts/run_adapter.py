#!/usr/bin/env python
"""Compatibility CLI wrapper for the internal adapter runner."""

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from adapter_runner import legacy_runner as _legacy_runner
from adapter_runner.legacy_runner import *  # noqa: F401,F403


_run_adapter_core = _legacy_runner._run_adapter_core


def main():
    _legacy_runner.main()


if __name__ == "__main__":
    main()

