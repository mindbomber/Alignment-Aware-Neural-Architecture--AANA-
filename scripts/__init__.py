"""Installable command modules for the AANA platform helpers.

The public layout keeps experiment, validation, integration, and pilot scripts
inside grouped subpackages. A few older tests and local snippets still import
script modules from `scripts` directly, so this module keeps import-only aliases
without recreating top-level executable files.
"""

from __future__ import annotations

from importlib import import_module


_ALIASES = {
    "build_family_pages": "scripts.publication.build_family_pages",
    "pilot_smoke_test": "scripts.pilots.pilot_smoke_test",
    "run_internal_pilot": "scripts.pilots.run_internal_pilot",
    "run_starter_pilot_kit": "scripts.pilots.run_starter_pilot_kit",
    "run_support_advisory_pilot": "scripts.pilots.run_support_advisory_pilot",
    "run_support_enforced_draft_pilot": "scripts.pilots.run_support_enforced_draft_pilot",
    "run_support_enforced_email_pilot": "scripts.pilots.run_support_enforced_email_pilot",
    "run_support_shadow_pilot": "scripts.pilots.run_support_shadow_pilot",
}


def __getattr__(name: str):
    if name in _ALIASES:
        module = import_module(_ALIASES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module 'scripts' has no attribute {name!r}")


__all__ = sorted(_ALIASES)
