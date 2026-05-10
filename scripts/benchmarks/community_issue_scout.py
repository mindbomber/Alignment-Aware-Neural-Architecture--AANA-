#!/usr/bin/env python
"""Find public community issues that are good candidates for AANA intake."""

import argparse
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request


DEFAULT_QUERIES = [
    '"agent tool" safety label:"help wanted" state:open',
    '"MCP" security state:open',
    '"LLM eval" harness label:"help wanted" state:open',
    '"audit log" agent state:open',
    '"authorization" "tool call" state:open',
    '"RAG" citation verification state:open',
]
DEFAULT_LIMIT = 5
GITHUB_SEARCH_URL = "https://api.github.com/search/issues"

TARGET_PR_AREAS = {
    "agent_tool_safety": [
        "agent tool safety",
        "tool safety",
        "tool call",
        "function calling",
        "tool use",
        "unsafe tool",
        "tool execution",
        "agent action",
    ],
    "mcp_security": [
        "mcp",
        "model context protocol",
        "mcp security",
        "tool injection",
        "prompt injection",
        "cross-boundary",
        "data exfiltration",
    ],
    "eval_harness": [
        "eval",
        "evaluation",
        "eval harness",
        "evaluation harness",
        "benchmark harness",
        "benchmark",
        "reproducible",
        "scorer",
        "grader",
        "test harness",
        "tests",
        "leaderboard",
        "metric",
    ],
    "audit_logging": [
        "audit log",
        "audit logging",
        "audit trail",
        "trace",
        "tracing",
        "observability",
        "provenance",
    ],
    "authorization_checks": [
        "authorization",
        "permission",
        "access control",
        "authenticated",
        "identity",
        "consent",
        "approval",
        "scope check",
    ],
    "groundedness_citation_verification": [
        "grounded",
        "groundedness",
        "citation",
        "citations",
        "source verification",
        "evidence",
        "hallucination",
        "unsupported answer",
        "rag",
    ],
}

TARGET_PR_AREA_ADAPTER = {
    "agent_tool_safety": "agent_action_safety_guardrail",
    "mcp_security": "agent_action_safety_guardrail",
    "eval_harness": "model_evaluation_release",
    "audit_logging": "code_change_review",
    "authorization_checks": "agent_action_safety_guardrail",
    "groundedness_citation_verification": "research_answer_grounding",
}

TARGET_PR_POLICY = {
    "required_direct_improvement_areas": sorted(TARGET_PR_AREAS),
    "avoid": [
        "random documentation polish",
        "broad speculative research comments",
        "taste-only UI changes",
        "unbounded product ideas",
        "repo changes where AANA is only mentioned but does not improve safety, evidence, authorization, auditability, or evaluation",
    ],
}


FAMILY_KEYWORDS = [
    (
        "mechanistic_interpretability",
        ["mechanistic interpretability", "interpretability", "circuit", "activation", "attention"],
    ),
    ("alignment_evaluation", ["ai alignment", "alignment", "safety", "drift", "eval", "benchmark", "harness"]),
    ("rag_grounding", ["rag", "retrieval", "hallucination", "citation", "grounding", "source"]),
    ("deployment_guardrail", ["deploy", "release", "ci", "github action", "guardrail", "production", "audit"]),
    ("agent_tool_control", ["tool call", "function calling", "agent action", "tool use", "mcp", "authorization"]),
    ("documentation", ["docs", "documentation", "readme", "guide", "tutorial"]),
]

ADAPTER_BY_FAMILY = {
    "mechanistic_interpretability": "research_answer_grounding",
    "alignment_evaluation": "model_evaluation_release",
    "rag_grounding": "research_answer_grounding",
    "deployment_guardrail": "code_change_review",
    "agent_tool_control": "agent_action_safety_guardrail",
    "documentation": "publication_check",
}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def labels_for(issue):
    return [label.get("name", "").lower() for label in issue.get("labels", []) if isinstance(label, dict)]


def text_for(issue):
    parts = [issue.get("title", ""), issue.get("body", "")]
    parts.extend(labels_for(issue))
    return " ".join(str(part) for part in parts if part).lower()


def keyword_matches(text, keyword):
    if " " in keyword:
        return keyword in text
    return bool(re.search(rf"\b{re.escape(keyword)}\b", text))


def repo_name(issue):
    if issue.get("repository_url"):
        return issue["repository_url"].rstrip("/").replace("https://api.github.com/repos/", "")
    url = issue.get("html_url", "")
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return ""


def classify_family(issue):
    text = text_for(issue)
    best_family = "community_research"
    best_score = 0
    for family, keywords in FAMILY_KEYWORDS:
        score = sum(1 for keyword in keywords if keyword_matches(text, keyword))
        if score > best_score:
            best_family = family
            best_score = score
    return best_family


def target_pr_area_scores(issue):
    text = text_for(issue)
    scores = {}
    for area, keywords in TARGET_PR_AREAS.items():
        score = sum(1 for keyword in keywords if keyword_matches(text, keyword))
        if score:
            scores[area] = score
    return scores


def primary_target_area(scores):
    if not scores:
        return ""
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]


def evidence_needed(issue, family):
    base = ["issue body", "maintainer acceptance criteria", "repository contribution rules"]
    if family == "mechanistic_interpretability":
        return base + ["model or architecture target", "experiment artifacts", "trace or benchmark expectation"]
    if family == "alignment_evaluation":
        return base + ["benchmark definition", "baseline results", "risk or failure-mode taxonomy"]
    if family == "rag_grounding":
        return base + ["allowed source corpus", "citation policy", "unsupported-answer behavior"]
    if family == "deployment_guardrail":
        return base + ["diff or release plan", "CI output", "rollback and owner evidence"]
    if family == "agent_tool_control":
        return base + ["tool-call surface", "authorization assumptions", "unsafe/private/write action examples"]
    if family == "documentation":
        return base + ["current docs page", "claim boundaries", "examples tied to one of the allowed PR areas"]
    return base


def score_issue(issue):
    text = text_for(issue)
    labels = labels_for(issue)
    family = classify_family(issue)
    target_scores = target_pr_area_scores(issue)
    target_area = primary_target_area(target_scores)
    score = 0

    if target_scores:
        score += 3
    if any(label in labels for label in ["help wanted", "good first issue", "good-first-issue", "contributions welcome"]):
        score += 2
    if "pull_request" not in issue:
        score += 1
    if family != "community_research":
        score += 2
    if any(keyword_matches(text, term) for term in ["benchmark", "citation", "evidence", "reproduce", "test", "eval", "docs"]):
        score += 1
    if any(keyword_matches(text, term) for term in ["private", "medical", "legal", "financial", "production", "security"]):
        score += 1
    if family == "documentation" and not target_scores:
        score = min(score, 2)
    if not target_scores:
        score = min(score, 2)

    if score >= 5:
        fit = "high"
    elif score >= 3:
        fit = "medium"
    else:
        fit = "low"

    first_action = "create workflow contract"
    if fit == "low":
        first_action = "ask clarifying question"
    elif target_area in {"groundedness_citation_verification", "eval_harness"} or family in {"rag_grounding", "alignment_evaluation"}:
        first_action = "draft grounded response and run workflow-check"
    elif target_area:
        first_action = "build minimal targeted PR plan and run workflow-check"

    return {
        "source": issue.get("html_url", ""),
        "repository": repo_name(issue),
        "problem": issue.get("title", "").strip(),
        "aana_fit": fit,
        "issue_family": family,
        "target_pr_area": target_area,
        "target_pr_area_scores": target_scores,
        "target_pr_eligible": bool(target_area) and fit in {"high", "medium"},
        "adapter": TARGET_PR_AREA_ADAPTER.get(target_area, ADAPTER_BY_FAMILY.get(family, "research_summary")),
        "labels": labels,
        "evidence_needed": evidence_needed(issue, family),
        "first_action": first_action,
        "publish_boundary": "public issue evidence only; no private data, random PRs, or unmeasured claims",
    }


def fetch_query(query, limit, token=None):
    params = urllib.parse.urlencode({"q": query, "per_page": str(limit)})
    request = urllib.request.Request(
        f"{GITHUB_SEARCH_URL}?{params}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "aana-community-issue-scout",
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("items", [])


def scout(queries, limit, fixture=None, token=None):
    issues = []
    if fixture:
        payload = load_json(fixture)
        issues = payload.get("items", payload if isinstance(payload, list) else [])
    else:
        for query in queries:
            issues.extend(fetch_query(query, limit, token=token))

    seen = set()
    candidates = []
    for issue in issues:
        key = issue.get("html_url") or issue.get("url")
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(score_issue(issue))
    return sorted(
        candidates,
        key=lambda item: (
            0 if item.get("target_pr_eligible") else 1,
            {"high": 0, "medium": 1, "low": 2}[item["aana_fit"]],
            -(item.get("target_pr_area_scores") or {}).get(item.get("target_pr_area", ""), 0),
        ),
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", dest="queries", help="GitHub issue search query. Can be repeated.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Results per query.")
    parser.add_argument("--fixture", help="Read GitHub search JSON from a local fixture instead of network.")
    parser.add_argument("--token", help="Optional GitHub token for higher API limits.")
    parser.add_argument("--output", help="Write candidate JSON to this path.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    candidates = scout(args.queries or DEFAULT_QUERIES, args.limit, fixture=args.fixture, token=args.token)
    text = json.dumps({"candidates": candidates}, indent=2, sort_keys=True)
    if args.output:
        output = pathlib.Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
