const DATA_URL = "/eval_outputs/demos/enterprise_support_flow/demo-flow.json";

const els = {
  pass: document.getElementById("stat-pass"),
  interventions: document.getElementById("stat-interventions"),
  aix: document.getElementById("stat-aix"),
  blockers: document.getElementById("stat-blockers"),
  generatedAt: document.getElementById("generated-at"),
  steps: document.getElementById("steps"),
  dashboard: document.getElementById("dashboard-json"),
  artifacts: document.getElementById("artifacts"),
  reportLink: document.getElementById("report-link"),
};

function numberValue(value) {
  return typeof value === "number" ? value : 0;
}

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function setText(element, value) {
  element.textContent = value == null ? "-" : String(value);
}

function renderSteps(steps) {
  els.steps.innerHTML = "";
  for (const step of steps) {
    const item = document.createElement("article");
    item.className = "step";

    const title = document.createElement("div");
    title.className = "step-title";
    const name = document.createElement("strong");
    name.textContent = step.title || step.adapter;
    const route = document.createElement("span");
    route.className = `pill ${step.aana_check?.recommended_action || ""}`;
    route.textContent = step.aana_check?.recommended_action || "unchecked";
    const action = document.createElement("p");
    action.textContent = step.ai_proposes_action || "";
    title.append(name, route, action);

    const preview = document.createElement("div");
    preview.className = "preview";
    preview.textContent = step.safe_output_preview || step.candidate_preview || "";

    const scores = document.createElement("div");
    scores.className = "score-box";
    const rows = [
      ["Gate", step.aana_check?.gate_decision],
      ["Final AIx", formatScore(step.aix?.score)],
      ["Candidate AIx", formatScore(step.aix?.candidate_score)],
      ["Violations", (step.aana_check?.violation_codes || []).length],
      ["Audit written", step.redacted_audit?.written ? "yes" : "no"],
    ];
    for (const [label, value] of rows) {
      const row = document.createElement("div");
      row.className = "score";
      const left = document.createElement("span");
      left.textContent = label;
      const right = document.createElement("strong");
      right.textContent = value == null ? "-" : String(value);
      row.append(left, right);
      scores.appendChild(row);
    }

    item.append(title, preview, scores);
    els.steps.appendChild(item);
  }
}

function renderArtifacts(artifacts) {
  els.artifacts.innerHTML = "";
  for (const [name, path] of Object.entries(artifacts || {})) {
    const row = document.createElement("div");
    row.className = "artifact";
    const label = document.createElement("span");
    label.textContent = name.replaceAll("_", " ");
    const value = document.createElement("code");
    value.textContent = path;
    row.append(label, value);
    els.artifacts.appendChild(row);
  }
}

function render(flow) {
  const cards = flow.dashboard_cards || {};
  const actionCounts = flow.dashboard_metrics?.recommended_actions || {};
  const interventions = Object.entries(actionCounts)
    .filter(([action]) => action !== "accept")
    .reduce((total, [, count]) => total + numberValue(count), 0);

  setText(els.pass, cards.pass);
  setText(els.interventions, interventions);
  setText(els.aix, formatScore(cards.aix_average));
  setText(els.blockers, cards.hard_blockers);
  setText(els.generatedAt, flow.created_at);
  renderSteps(flow.steps || []);
  els.dashboard.textContent = JSON.stringify(
    {
      cards: flow.dashboard_cards,
      recommended_actions: flow.dashboard_metrics?.recommended_actions,
      top_violations: flow.dashboard_metrics?.top_violations,
      aix_report_summary: flow.aix_report_summary,
    },
    null,
    2
  );
  renderArtifacts(flow.artifacts);
}

async function loadFlow() {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Demo data not found. Run: python scripts/aana_cli.py enterprise-support-demo`);
  }
  return response.json();
}

loadFlow()
  .then(render)
  .catch((error) => {
    els.steps.innerHTML = `<div class="error">${error.message}</div>`;
    els.dashboard.textContent = "";
  });
