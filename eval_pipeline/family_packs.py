"""Family pack metadata for productized AANA adapter surfaces."""

from __future__ import annotations

import html
import json
import pathlib

from eval_pipeline import adapter_gallery
from aana.bundles import canonicalize_bundle_id


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_KIT_ROOT = ROOT / "examples" / "starter_pilot_kits"
DEFAULT_OUTPUT_ROOT = ROOT / "docs"
FAMILY_PACK_VERSION = "0.1"

FAMILY_DEFINITIONS = {
    "enterprise": {
        "slug": "enterprise",
        "gallery_pack": "enterprise",
        "title": "Enterprise AANA Pack",
        "eyebrow": "Enterprise family",
        "starter_kit": "enterprise",
        "boundary": "Operational risk before customer, code, deployment, data, access, billing, and incident actions.",
        "best_for": [
            "support teams checking customer-visible replies",
            "engineering teams reviewing code, API, database, infrastructure, and deployment changes",
            "security, IAM, data, and incident reviewers who need evidence-backed approval routes",
        ],
        "not_for": [
            "replacing production authorization, CI, deployment, or ticketing systems",
            "making regulated decisions without reviewed evidence connectors and human-review routing",
        ],
        "primary_surfaces": ["Docker HTTP bridge", "web playground", "GitHub Action", "shadow mode", "metrics dashboard"],
    },
    "personal_productivity": {
        "slug": "personal-productivity",
        "gallery_pack": "personal_productivity",
        "title": "Personal Productivity AANA Pack",
        "eyebrow": "Personal productivity family",
        "starter_kit": "personal_productivity",
        "boundary": "Irreversible personal actions before send, schedule, delete, move, write, buy, publish, or cite.",
        "best_for": [
            "local assistants that draft emails, calendar invites, file operations, bookings, and research answers",
            "users who want observe-only checks before actions that are hard to undo",
            "synthetic local demos that avoid real sends, deletes, purchases, or private data",
        ],
        "not_for": [
            "silently taking direct action on behalf of a user",
            "storing private local content in audit records",
        ],
        "primary_surfaces": ["local desktop/browser demos", "web playground", "Docker HTTP bridge", "shadow mode"],
    },
    "government_civic": {
        "slug": "government-civic",
        "gallery_pack": "government_civic",
        "title": "Government And Civic AANA Pack",
        "eyebrow": "Government and civic family",
        "starter_kit": "civic_government",
        "boundary": "Public-service, procurement, grant, records, privacy, eligibility, policy, and public-communication workflows.",
        "best_for": [
            "procurement and grant reviewers checking eligibility, scoring, vendor, privacy, and policy boundaries",
            "records, policy, and public-communications teams that need source-grounded reviewer handoff",
            "benefits or legal-adjacent triage where AANA should route to general information, ask, defer, or human review",
        ],
        "not_for": [
            "final eligibility, legal, procurement, or benefits determinations without authorized human review",
            "handling real public records before redaction, retention, jurisdiction, and source-law policies are approved",
        ],
        "primary_surfaces": ["web playground", "Workflow Contract", "shadow mode", "redacted audit metrics"],
    },
}


def load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _kit_path(family_id, kit_root=DEFAULT_KIT_ROOT):
    family_id = canonicalize_bundle_id(family_id)
    return pathlib.Path(kit_root) / FAMILY_DEFINITIONS[family_id]["starter_kit"]


def _workflow_specs(family_id, kit_root=DEFAULT_KIT_ROOT):
    family_id = canonicalize_bundle_id(family_id)
    payload = load_json(_kit_path(family_id, kit_root) / "workflows.json")
    workflows = payload.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        raise ValueError(f"{family_id} workflows.json must include a non-empty workflows list.")
    return workflows


def _adapter_cards_by_id(gallery_payload):
    return {card["id"]: card for card in gallery_payload.get("adapters", [])}


def _ordered_adapter_cards(family_id, gallery_payload, kit_root=DEFAULT_KIT_ROOT):
    family_id = canonicalize_bundle_id(family_id)
    cards = _adapter_cards_by_id(gallery_payload)
    ordered = []
    seen = set()
    for workflow in _workflow_specs(family_id, kit_root):
        adapter_id = workflow.get("adapter_id")
        if adapter_id in seen:
            continue
        if adapter_id not in cards:
            raise ValueError(f"{family_id} starter kit references unknown adapter: {adapter_id}")
        seen.add(adapter_id)
        ordered.append(cards[adapter_id])
    return ordered


def family_pack(family_id, gallery_payload=None, kit_root=DEFAULT_KIT_ROOT):
    family_id = canonicalize_bundle_id(family_id)
    if family_id not in FAMILY_DEFINITIONS:
        raise ValueError(f"Unknown family id: {family_id}")
    gallery_payload = gallery_payload or adapter_gallery.published_gallery()
    definition = FAMILY_DEFINITIONS[family_id]
    kit_path = _kit_path(family_id, kit_root)
    manifest = load_json(kit_path / "manifest.json")
    workflows = _workflow_specs(family_id, kit_root)
    cards = _ordered_adapter_cards(family_id, gallery_payload, kit_root)
    risk_tier_counts = {}
    evidence = []
    for card in cards:
        risk_tier_counts[card["risk_tier"]] = risk_tier_counts.get(card["risk_tier"], 0) + 1
        evidence.extend(card.get("required_evidence", []))
    return {
        "family_pack_version": FAMILY_PACK_VERSION,
        "family_id": family_id,
        "slug": definition["slug"],
        "gallery_pack": definition["gallery_pack"],
        "title": definition["title"],
        "eyebrow": definition["eyebrow"],
        "boundary": definition["boundary"],
        "best_for": definition["best_for"],
        "not_for": definition["not_for"],
        "primary_surfaces": definition["primary_surfaces"],
        "adapter_count": len(cards),
        "workflow_count": len(workflows),
        "risk_tier_counts": dict(sorted(risk_tier_counts.items())),
        "required_evidence": sorted(set(evidence), key=str.lower),
        "starter_kit": {
            "id": manifest.get("id"),
            "title": manifest.get("title"),
            "goal": manifest.get("goal"),
            "command": f"python scripts/run_starter_pilot_kit.py --kit {manifest.get('id')}",
            "output_dir": manifest.get("default_output_dir"),
            "files": manifest.get("files", {}),
            "path": str(kit_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "adapters": cards,
    }


def family_packs(gallery_payload=None, kit_root=DEFAULT_KIT_ROOT):
    gallery_payload = gallery_payload or adapter_gallery.published_gallery()
    return {
        "family_packs_version": FAMILY_PACK_VERSION,
        "families": [family_pack(family_id, gallery_payload, kit_root) for family_id in FAMILY_DEFINITIONS],
    }


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _list_html(items):
    return "\n".join(f"<li>{_esc(item)}</li>" for item in items)


def _risk_counts_html(counts):
    return " ".join(f'<span class="chip {tier}">{_esc(tier)}: {_esc(count)}</span>' for tier, count in counts.items())


def render_family_page(pack):
    adapter_cards = []
    for adapter in pack["adapters"]:
        expected = adapter.get("example_outputs", {}).get("expected", {})
        evidence = adapter.get("required_evidence", [])
        evidence_preview = evidence[:5]
        more = len(evidence) - len(evidence_preview)
        if more > 0:
            evidence_preview.append(f"+{more} more evidence source(s)")
        adapter_cards.append(
            f"""
            <article class="adapter-card">
              <div class="card-top">
                <div>
                  <h3>{_esc(adapter["title"])}</h3>
                  <p>{_esc(adapter["workflow"])}</p>
                </div>
                <span class="chip {adapter["risk_tier"]}">{_esc(adapter["risk_tier"])}</span>
              </div>
              <div class="split">
                <div>
                  <h4>Required evidence</h4>
                  <ul>{_list_html(evidence_preview)}</ul>
                </div>
                <div>
                  <h4>Expected outcome</h4>
                  <dl>
                    <dt>Gate</dt><dd>{_esc(expected.get("gate_decision"))}</dd>
                    <dt>Action</dt><dd>{_esc(expected.get("recommended_action"))}</dd>
                    <dt>Candidate</dt><dd>{_esc(expected.get("candidate_gate"))}</dd>
                  </dl>
                </div>
              </div>
              <div class="actions">
                <a class="button primary" href="/playground?adapter={_esc(adapter["id"])}">Try this adapter</a>
                <a class="button" href="/adapter-gallery?adapter={_esc(adapter["id"])}">View in gallery</a>
              </div>
            </article>
            """
        )
    pack_json = json.dumps(pack, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_esc(pack["title"])}</title>
    <meta name="description" content="{_esc(pack["boundary"])}">
    <link rel="stylesheet" href="../families/family-pack.css">
  </head>
  <body>
    <main class="shell">
      <header class="hero">
        <div>
          <p class="eyebrow">{_esc(pack["eyebrow"])}</p>
          <h1>{_esc(pack["title"])}</h1>
          <p>{_esc(pack["boundary"])}</p>
        </div>
        <div class="hero-actions">
          <a class="button primary" href="/adapter-gallery?pack={_esc(pack["gallery_pack"])}">Browse adapters</a>
          <a class="button" href="/playground?adapter={_esc(pack["adapters"][0]["id"])}">Run first example</a>
        </div>
      </header>

      <section class="summary" aria-label="Family summary">
        <article><span>{pack["adapter_count"]}</span><strong>adapters</strong></article>
        <article><span>{pack["workflow_count"]}</span><strong>starter workflows</strong></article>
        <article><span>{len(pack["required_evidence"])}</span><strong>evidence types</strong></article>
        <article><span>{len(pack["primary_surfaces"])}</span><strong>surfaces</strong></article>
      </section>

      <section class="grid two">
        <article class="panel">
          <h2>Product Boundary</h2>
          <p>{_esc(pack["boundary"])}</p>
          <h3>Best for</h3>
          <ul>{_list_html(pack["best_for"])}</ul>
        </article>
        <article class="panel">
          <h2>Guardrails</h2>
          <div class="chips">{_risk_counts_html(pack["risk_tier_counts"])}</div>
          <h3>Not for</h3>
          <ul>{_list_html(pack["not_for"])}</ul>
        </article>
      </section>

      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Starter Pilot Kit</h2>
            <p>{_esc(pack["starter_kit"]["goal"])}</p>
          </div>
          <a class="button primary" href="/playground?adapter={_esc(pack["adapters"][0]["id"])}">Try in browser</a>
        </div>
        <pre>{_esc(pack["starter_kit"]["command"])}</pre>
        <p class="muted">Synthetic data, adapter config, workflow examples, expected outcomes, redacted audit logs, metrics report, and Markdown/JSON reports are generated under <code>{_esc(pack["starter_kit"]["output_dir"])}</code>.</p>
      </section>

      <section>
        <div class="section-head">
          <div>
            <h2>Adapters</h2>
            <p>Each adapter card links to a runnable playground example and shows risk tier, evidence, and expected gate/action behavior.</p>
          </div>
        </div>
        <div class="adapter-grid">
          {"".join(adapter_cards)}
        </div>
      </section>

      <section class="panel">
        <h2>Pack Metadata</h2>
        <pre>{_esc(pack_json)}</pre>
      </section>
    </main>
  </body>
</html>
"""


def write_family_pages(output_root=DEFAULT_OUTPUT_ROOT, gallery_payload=None, kit_root=DEFAULT_KIT_ROOT):
    payload = family_packs(gallery_payload=gallery_payload, kit_root=kit_root)
    output_root = pathlib.Path(output_root)
    (output_root / "families").mkdir(parents=True, exist_ok=True)
    (output_root / "families" / "data.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for pack in payload["families"]:
        page_dir = output_root / pack["slug"]
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(render_family_page(pack), encoding="utf-8")
    return payload
