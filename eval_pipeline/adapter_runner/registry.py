"""Adapter registry and adapter metadata helpers."""

import json
import pathlib


def load_adapter(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        adapter = json.load(handle)
    if not isinstance(adapter, dict):
        raise ValueError("Adapter file must contain a JSON object.")
    if not adapter.get("adapter_name"):
        raise ValueError("Adapter file is missing adapter_name.")
    return adapter


def adapter_summary(adapter):
    return {
        "name": adapter.get("adapter_name"),
        "version": adapter.get("version"),
        "domain": adapter.get("domain", {}).get("name"),
    }

