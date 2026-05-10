#!/usr/bin/env python3
"""Run a conservative repo-local secrets scan with an explicit deployment allowlist."""

from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ALLOWLIST = ROOT / "examples" / "secrets_scan_allowlist.json"
DEFAULT_SCAN_TARGETS = [
    "deploy",
    "docs",
    "eval_pipeline",
    "examples",
    "scripts",
    "tests",
    "README.md",
    "SECURITY.md",
]
EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "eval_outputs",
    "node_modules",
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".env",
    ".example",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SECRET_PATTERNS = [
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|auth[_-]?token|token|secret|password|client[_-]?secret)\b"
            r"\s*[:=]\s*[\"']?([^\"'\s,}]+)"
        ),
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+([A-Za-z0-9._~+/=-]{8,})"),
    ),
]
SAFE_VALUE_PREFIXES = (
    "<",
    "[",
    "${",
    "$(",
    "AANA_",
    "replace-",
    "redacted",
    "none",
    "null",
    "true",
    "false",
)
SAFE_CODE_REFERENCES = (
    "args.",
    "auth_token",
    "match.",
    "os.environ",
    "responses_api_config",
    "result[",
    "secrets.",
    "self.",
    "_resolved",
    "process.env.",
)


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_rel(path):
    return path.relative_to(ROOT).as_posix()


def _is_text_file(path):
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.endswith(".env.example")


def _iter_files(targets):
    for target in targets:
        path = ROOT / target
        if not path.exists():
            continue
        if path.is_file():
            if _is_text_file(path):
                yield path
            continue
        for child in path.rglob("*"):
            if child.is_dir():
                continue
            if any(part in EXCLUDED_DIRS for part in child.relative_to(ROOT).parts):
                continue
            if _is_text_file(child):
                yield child


def _safe_value(value):
    normalized = str(value or "").strip().strip("\"'").strip()
    if len(normalized) < 8:
        return True
    lower = normalized.lower()
    if normalized.startswith(SAFE_VALUE_PREFIXES) or lower in SAFE_VALUE_PREFIXES:
        return True
    if any(reference in normalized for reference in SAFE_CODE_REFERENCES):
        return True
    if any(character in normalized for character in "()[]{}"):
        return True
    return False


def _line_findings(path, line_number, line):
    for pattern_id, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(line):
            secret = match.group(2) if pattern_id == "credential_assignment" else match.group(1)
            if _safe_value(secret):
                continue
            yield {
                "path": _repo_rel(path),
                "line": line_number,
                "pattern_id": pattern_id,
                "secret_preview": f"{secret[:3]}...{secret[-2:]}",
                "line_excerpt": line.strip()[:1000],
            }


def _allowed(finding, allowlist):
    for item in allowlist:
        path_pattern = item.get("path")
        text_pattern = item.get("match")
        pattern_id = item.get("pattern_id")
        if path_pattern and not fnmatch.fnmatch(finding["path"], path_pattern):
            continue
        if pattern_id and finding["pattern_id"] != pattern_id:
            continue
        if text_pattern and text_pattern not in finding["line_excerpt"]:
            continue
        return True
    return False


def scan(allowlist_path=DEFAULT_ALLOWLIST, targets=None):
    allowlist_payload = _load_json(pathlib.Path(allowlist_path))
    allowlist = allowlist_payload.get("allowlist", [])
    scan_targets = targets or allowlist_payload.get("scan_targets") or DEFAULT_SCAN_TARGETS
    findings = []
    allowed_findings = []
    for path in sorted(set(_iter_files(scan_targets))):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for finding in _line_findings(path, line_number, line):
                if _allowed(finding, allowlist):
                    allowed_findings.append(finding)
                else:
                    findings.append(finding)
    return {
        "valid": not findings,
        "unapproved_findings": findings,
        "allowed_findings": allowed_findings,
        "allowlist": _repo_rel(pathlib.Path(allowlist_path)),
        "scanned_targets": scan_targets,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="Secrets scan allowlist JSON.")
    parser.add_argument("--target", action="append", dest="targets", help="Repo-relative path to scan. Repeatable.")
    args = parser.parse_args(argv)

    report = scan(allowlist_path=args.allowlist, targets=args.targets)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
