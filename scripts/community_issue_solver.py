#!/usr/bin/env python
"""Create AANA-gated workpacks for public GitHub issues."""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = ROOT / "examples" / "community_issue_candidates.json"
DEFAULT_OUTPUT_DIR = ROOT / "eval_outputs" / "community_issue_solver"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "audit" / "community-issue-solver.jsonl"
DEFAULT_ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "defer", "refuse"]


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:80] or "issue"


def parse_issue_url(url):
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(parts) >= 4 and parts[2] == "issues":
        return parts[0], parts[1], parts[3]
    raise ValueError(f"unsupported GitHub issue URL: {url}")


def fetch_issue(url, token=None):
    owner, repo, issue_number = parse_issue_url(url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "aana-community-issue-solver",
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def labels_for_issue(issue):
    return [label.get("name", "") for label in issue.get("labels", []) if isinstance(label, dict)]


def compact(text, limit=4000):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated at {limit} characters]"


def first_contribution(candidate):
    family = candidate.get("issue_family", "")
    if family == "alignment_evaluation":
        return (
            "a taxonomy-to-constraint map plus a small fixture-backed scoring checklist that maintainers can review "
            "before any deeper integration"
        )
    if family == "rag_grounding":
        return (
            "a source-grounding test fixture that checks citation boundaries, unsupported-answer behavior, and "
            "uncertainty labeling"
        )
    if family == "mechanistic_interpretability":
        return (
            "a reproducible experiment-plan checklist that separates observable traces, claims, evidence, and "
            "non-claims before implementation"
        )
    if family == "deployment_guardrail":
        return "a CI guardrail fixture that checks tests, rollback evidence, secrets, and risky release claims"
    if family == "documentation":
        return "a documentation patch that narrows claims, adds evidence boundaries, and includes a minimal example"
    return "a narrow public-evidence checklist and Workflow Contract that maintainers can review"


def draft_public_response(candidate, issue):
    title = issue.get("title") or candidate.get("problem", "")
    contribution = first_contribution(candidate)
    repo = candidate.get("repository", "")
    source = candidate.get("source", "")
    return f"""Hi, I found this while testing an AANA-gated community issue workflow.

For this issue, I think the most useful first contribution is {contribution}.

AANA would not replace {repo}'s implementation or act as a compliance authority. The useful role here is narrower: turn the issue scope into explicit constraints, attach public evidence, run a verifier/correction gate before publishing claims or code, and keep an audit-safe record of the decision route.

For this issue, I would start with:

- map the requested scope into factual, human-impact, repository, and evidence-integrity constraints
- add a small fixture or checklist that maintainers can inspect in one review
- avoid legal, regulatory, benchmark, or production-readiness claims that are not directly supported by the issue evidence
- ask for repository-specific acceptance criteria before proposing deeper integration

Evidence limits:

- I am using only the public issue text and repository metadata visible from the issue.
- I have not verified the repository architecture, existing scoring code, tests, or maintainers' preferred implementation path.
- This is not a claim that AANA certifies compliance, proves alignment, or replaces the project's risk engine.

If that direction fits, I can prepare the first small artifact as a reviewable PR or issue comment. Source issue checked: {source}
"""


def build_workflow_contract(candidate, issue, draft):
    source = candidate.get("source", "")
    labels = ", ".join(labels_for_issue(issue) or candidate.get("labels", [])) or "none"
    body = compact(issue.get("body", ""), limit=5000)
    title = issue.get("title") or candidate.get("problem", "")
    return {
        "contract_version": "0.1",
        "workflow_id": f"community-solver-{slugify(candidate.get('repository', 'repo'))}-{slugify(title)}",
        "adapter": "research_answer_grounding",
        "request": (
            "Check this public GitHub issue response before posting. The response should help solve the issue, "
            "make AANA's role discoverable, avoid unsupported claims, and stay inside public evidence and maintainer scope."
        ),
        "candidate": draft,
        "evidence": [
            f"Source URL: {source}",
            f"Repository: {candidate.get('repository', '')}",
            f"Issue title: {title}",
            f"Issue labels: {labels}",
            f"Issue body excerpt:\n{body or 'No body available.'}",
            f"Scout issue family: {candidate.get('issue_family', '')}",
            f"Scout suggested adapter: {candidate.get('adapter', '')}",
            "AANA platform boundary: AANA is a runtime verifier/correction and gate layer; it does not guarantee alignment, compliance, legal correctness, or production readiness by itself.",
        ],
        "constraints": [
            "Do not claim AANA guarantees alignment, compliance, correctness, or mechanistic interpretability success.",
            "Do not make legal, medical, financial, security, benchmark, or production-readiness claims without issue evidence.",
            "Stay within the public issue scope and repository contribution boundaries.",
            "Make AANA discoverable by explaining the narrow verifier-gate contribution in practical terms.",
            "Propose a small reviewable first contribution before proposing broad integration.",
            "Ask maintainers for missing acceptance criteria instead of assuming repository architecture.",
        ],
        "allowed_actions": DEFAULT_ALLOWED_ACTIONS,
        "metadata": {
            "source_type": "github_issue",
            "source_url": source,
            "issue_family": candidate.get("issue_family", ""),
            "policy_preset": "research_answer_grounding",
            "publish_boundary": "public_issue_comment_or_pr_plan_only_after_aana_accept",
        },
    }


def run_aana(workflow_path, audit_log):
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "aana_cli.py"),
        "workflow-check",
        "--workflow",
        str(workflow_path),
        "--audit-log",
        str(audit_log),
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    try:
        result["json"] = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result["json"] = None
    return result


def select_candidates(candidates, repository=None, source=None, limit=1):
    selected = []
    for candidate in candidates:
        if repository and candidate.get("repository", "").lower() != repository.lower():
            continue
        if source and candidate.get("source", "") != source:
            continue
        if candidate.get("aana_fit") == "low":
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def create_workpack(candidate, output_dir, token=None, audit_log=DEFAULT_AUDIT_LOG, run_gate=True):
    issue = fetch_issue(candidate["source"], token=token)
    title = issue.get("title") or candidate.get("problem", "issue")
    workpack_dir = pathlib.Path(output_dir) / f"{slugify(candidate.get('repository', 'repo'))}-{slugify(title)}"
    workpack_dir.mkdir(parents=True, exist_ok=True)

    draft = draft_public_response(candidate, issue)
    contract = build_workflow_contract(candidate, issue, draft)
    workflow_path = workpack_dir / "workflow_contract.json"
    draft_path = workpack_dir / "issue_response_draft.md"
    readme_path = workpack_dir / "README.md"
    gate_path = workpack_dir / "aana_gate_result.json"

    write_json(workflow_path, contract)
    draft_path.write_text(draft, encoding="utf-8")
    readme_path.write_text(
        f"""# AANA Community Issue Workpack

Source: {candidate.get('source', '')}
Repository: {candidate.get('repository', '')}
Issue: {title}
AANA fit: {candidate.get('aana_fit', '')}
Issue family: {candidate.get('issue_family', '')}

Files:

- `workflow_contract.json` - AANA Workflow Contract for the proposed public response.
- `issue_response_draft.md` - Candidate issue response. Do not post unless the AANA result routes to accept.
- `aana_gate_result.json` - Gate output, when `--no-aana` is not used.

Publish boundary: {candidate.get('publish_boundary', '')}
""",
        encoding="utf-8",
    )

    gate_result = None
    if run_gate:
        gate_result = run_aana(workflow_path, pathlib.Path(audit_log))
        write_json(gate_path, gate_result)

    gate_json = (gate_result or {}).get("json") or {}
    return {
        "workpack_dir": str(workpack_dir),
        "workflow": str(workflow_path),
        "draft": str(draft_path),
        "gate_result": str(gate_path) if gate_result else "",
        "aana_recommended_action": gate_json.get("recommended_action") if gate_result else None,
        "aana_candidate_gate": gate_json.get("candidate_gate") if gate_result else None,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES), help="Candidate JSON from community_issue_scout.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for generated workpacks.")
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG), help="Redacted AANA audit JSONL path.")
    parser.add_argument("--repository", help="Only solve an issue from this owner/repo.")
    parser.add_argument("--source", help="Only solve this exact issue URL.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum workpacks to create.")
    parser.add_argument("--token", help="Optional GitHub token for API requests.")
    parser.add_argument("--no-aana", action="store_true", help="Create workpack without running workflow-check.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    payload = load_json(args.candidates)
    candidates = payload.get("candidates", payload if isinstance(payload, list) else [])
    selected = select_candidates(candidates, repository=args.repository, source=args.source, limit=args.limit)
    if not selected:
        print("No matching medium/high-fit candidates found.", file=sys.stderr)
        return 2
    workpacks = [
        create_workpack(
            candidate,
            output_dir=args.output_dir,
            token=args.token,
            audit_log=pathlib.Path(args.audit_log),
            run_gate=not args.no_aana,
        )
        for candidate in selected
    ]
    print(json.dumps({"workpacks": workpacks}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
