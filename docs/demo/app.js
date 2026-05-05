const state = {
  manifest: null,
  selected: null,
  selectedFamily: "enterprise",
};

const els = {
  list: document.getElementById("scenario-list"),
  familyTabs: document.getElementById("family-tabs"),
  category: document.getElementById("scenario-category"),
  title: document.getElementById("scenario-title"),
  workflow: document.getElementById("scenario-workflow"),
  request: document.getElementById("request-text"),
  candidate: document.getElementById("candidate-text"),
  evidence: document.getElementById("evidence-text"),
  run: document.getElementById("run-demo"),
  result: document.getElementById("result-section"),
  gate: document.getElementById("gate-decision"),
  action: document.getElementById("recommended-action"),
  aix: document.getElementById("aix-score"),
  candidateAix: document.getElementById("candidate-aix-score"),
  violations: document.getElementById("violations"),
  safeResponse: document.getElementById("safe-response"),
  metadata: document.getElementById("decision-metadata"),
};

function formatCategory(value) {
  return String(value || "").replace(/_/g, " ");
}

function familyTitle(id) {
  const family = (state.manifest?.families || []).find((item) => item.id === id);
  return family?.title || formatCategory(id);
}

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function renderFamilyTabs() {
  els.familyTabs.replaceChildren();
  for (const family of state.manifest.families || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `family-tab ${state.selectedFamily === family.id ? "active" : ""}`.trim();
    button.role = "tab";
    button.textContent = family.title;
    button.addEventListener("click", () => {
      state.selectedFamily = family.id;
      const first = state.manifest.scenarios.find((item) => item.family === family.id);
      selectScenario(first?.id);
      renderFamilyTabs();
    });
    els.familyTabs.appendChild(button);
  }
}

function renderScenarioButtons() {
  els.list.replaceChildren();
  for (const scenario of state.manifest.scenarios.filter((item) => item.family === state.selectedFamily)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `scenario-button ${state.selected?.id === scenario.id ? "active" : ""}`.trim();
    const title = document.createElement("strong");
    title.textContent = scenario.title;
    const category = document.createElement("span");
    category.textContent = `${familyTitle(scenario.family)} / ${formatCategory(scenario.category)}`;
    button.append(title, category);
    button.addEventListener("click", () => selectScenario(scenario.id));
    els.list.appendChild(button);
  }
}

function selectScenario(id) {
  const scenario = state.manifest.scenarios.find((item) => item.id === id);
  if (!scenario) return;
  state.selected = scenario;
  state.selectedFamily = scenario.family || state.selectedFamily;
  els.category.textContent = `${familyTitle(scenario.family)} / ${formatCategory(scenario.category)}`;
  els.title.textContent = scenario.title;
  els.workflow.textContent = scenario.workflow;
  els.request.textContent = scenario.request;
  els.candidate.textContent = scenario.candidate;
  els.evidence.textContent = scenario.evidence;
  els.result.hidden = true;
  renderScenarioButtons();
}

function renderViolations(violations) {
  els.violations.replaceChildren();
  for (const violation of violations || []) {
    const item = document.createElement("div");
    item.className = "violation";
    const title = document.createElement("strong");
    title.textContent = `${violation.code} - ${violation.severity}`;
    const message = document.createElement("span");
    message.textContent = violation.message;
    item.append(title, message);
    els.violations.appendChild(item);
  }
}

function runSyntheticCheck() {
  if (!state.selected) return;
  const result = state.selected.result;
  els.gate.textContent = result.gate_decision;
  els.action.textContent = result.recommended_action;
  els.aix.textContent = `${formatScore(result.aix_score)} ${result.aix_decision}`;
  els.candidateAix.textContent = `${formatScore(result.candidate_aix_score)} ${result.candidate_aix_decision}`;
  renderViolations(result.violations);
  els.safeResponse.textContent = result.safe_response;
  els.metadata.textContent = JSON.stringify(
    {
      runtime_mode: state.manifest.runtime_mode,
      synthetic_only: state.manifest.synthetic_only,
      secrets_required: state.manifest.secrets_required,
      real_side_effects: state.manifest.real_side_effects,
      candidate_gate: result.candidate_gate,
      hard_blockers: result.hard_blockers,
      blocked_capabilities: state.manifest.blocked_capabilities,
      docker_local_pilot: state.manifest.local_pilot_path,
    },
    null,
    2
  );
  els.result.hidden = false;
}

async function init() {
  const response = await fetch("scenarios.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Unable to load hosted demo scenarios: ${response.status}`);
  state.manifest = await response.json();
  state.selectedFamily = state.manifest.families?.[0]?.id || "enterprise";
  renderFamilyTabs();
  renderScenarioButtons();
  selectScenario(state.manifest.scenarios[0].id);
  els.run.addEventListener("click", runSyntheticCheck);
}

init().catch((error) => {
  els.title.textContent = "Demo unavailable";
  els.workflow.textContent = error.message;
  els.run.disabled = true;
});
