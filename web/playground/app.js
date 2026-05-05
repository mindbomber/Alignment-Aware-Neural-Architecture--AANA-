const DEFAULT_ALLOWED = ["accept", "revise", "retrieve", "ask", "defer", "refuse"];
const ACTION_PRESETS = {
  all: DEFAULT_ALLOWED,
  "no-accept": ["revise", "retrieve", "ask", "defer", "refuse"],
  "human-review": ["ask", "defer", "refuse"],
};

const state = {
  gallery: [],
  selected: null,
  lastResult: null,
};

const els = {
  token: document.getElementById("token"),
  saveToken: document.getElementById("save-token"),
  filter: document.getElementById("adapter-filter"),
  adapterList: document.getElementById("adapter-list"),
  adapterTitle: document.getElementById("adapter-title"),
  adapterWorkflow: document.getElementById("adapter-workflow"),
  request: document.getElementById("request"),
  candidate: document.getElementById("candidate"),
  evidence: document.getElementById("evidence"),
  constraints: document.getElementById("constraints"),
  allowedAction: document.getElementById("allowed-action"),
  resetDemo: document.getElementById("reset-demo"),
  runCheck: document.getElementById("run-check"),
  gate: document.getElementById("gate"),
  action: document.getElementById("action"),
  aixScore: document.getElementById("aix-score"),
  candidateAixScore: document.getElementById("candidate-aix-score"),
  violations: document.getElementById("violations"),
  safeResponse: document.getElementById("safe-response"),
  aixDetails: document.getElementById("aix-details"),
  auditRecord: document.getElementById("audit-record"),
};

function loadToken() {
  const saved = window.localStorage.getItem("aana.playground.token");
  els.token.value = saved || "aana-local-dev-token";
}

function authHeaders() {
  const token = els.token.value.trim();
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function splitLines(value) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function setMetric(element, value, className) {
  const parent = element.closest(".metric");
  parent.className = `metric ${className || ""}`.trim();
  element.textContent = value ?? "-";
}

function selectedAllowedActions() {
  return ACTION_PRESETS[els.allowedAction.value] || DEFAULT_ALLOWED;
}

function requestedAdapterId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("adapter") || params.get("adapter_id") || "";
}

function buildRequest() {
  const adapter = state.selected;
  return {
    contract_version: "0.1",
    workflow_id: `playground-${adapter.id}`,
    adapter: adapter.id,
    request: els.request.value,
    candidate: els.candidate.value,
    evidence: splitLines(els.evidence.value),
    constraints: splitLines(els.constraints.value),
    allowed_actions: selectedAllowedActions(),
    metadata: {
      surface: "aana_web_playground",
      gallery_title: adapter.title,
      policy_preset: adapter.id,
    },
  };
}

function renderAdapters() {
  const filter = els.filter.value.trim().toLowerCase();
  const items = state.gallery.filter((entry) => {
    const haystack = `${entry.id} ${entry.title} ${entry.workflow} ${(entry.best_for || []).join(" ")}`.toLowerCase();
    return haystack.includes(filter);
  });
  els.adapterList.innerHTML = "";
  for (const entry of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `adapter-card ${state.selected && state.selected.id === entry.id ? "active" : ""}`;
    const title = document.createElement("strong");
    title.textContent = entry.title;
    const id = document.createElement("span");
    id.textContent = entry.id;
    const workflow = document.createElement("span");
    workflow.textContent = entry.workflow;
    button.append(title, id, workflow);
    button.addEventListener("click", () => selectAdapter(entry.id));
    els.adapterList.appendChild(button);
  }
}

function selectAdapter(adapterId) {
  const entry = state.gallery.find((item) => item.id === adapterId);
  if (!entry) return;
  state.selected = entry;
  els.adapterTitle.textContent = entry.title;
  els.adapterWorkflow.textContent = entry.workflow;
  resetDemo();
  renderAdapters();
}

function resetDemo() {
  if (!state.selected) return;
  els.request.value = state.selected.prompt || "";
  els.candidate.value = state.selected.bad_candidate || "";
  els.evidence.value = "";
  els.constraints.value = "";
  els.allowedAction.value = "all";
  clearResults();
}

function clearResults() {
  setMetric(els.gate, "-", "");
  setMetric(els.action, "-", "");
  setMetric(els.aixScore, "-", "");
  setMetric(els.candidateAixScore, "-", "");
  els.violations.className = "empty";
  els.violations.textContent = "Run a check to see verifier findings.";
  els.safeResponse.textContent = "Run a check to see the corrected output.";
  els.aixDetails.textContent = "Run a check to inspect score, decision, components, thresholds, and hard blockers.";
  els.auditRecord.textContent = "Run a check to preview the audit record written by the bridge.";
}

function renderViolations(violations) {
  if (!violations || violations.length === 0) {
    els.violations.className = "empty";
    els.violations.textContent = "No violations in the final gated output.";
    return;
  }
  els.violations.className = "";
  els.violations.innerHTML = "";
  for (const violation of violations) {
    const item = document.createElement("div");
    item.className = "violation";
    const title = document.createElement("strong");
    title.textContent = `${violation.code || "violation"} - ${violation.severity || "unknown"}`;
    const message = document.createElement("span");
    message.textContent = violation.message || "";
    item.append(title, message);
    els.violations.appendChild(item);
  }
}

function renderResult(payload) {
  const result = payload.result || payload;
  state.lastResult = result;
  setMetric(els.gate, result.gate_decision, result.gate_decision);
  setMetric(els.action, result.recommended_action, result.recommended_action);
  setMetric(els.aixScore, result.aix && typeof result.aix.score === "number" ? result.aix.score.toFixed(3) : "-", result.aix?.decision);
  setMetric(
    els.candidateAixScore,
    result.candidate_aix && typeof result.candidate_aix.score === "number" ? result.candidate_aix.score.toFixed(3) : "-",
    result.candidate_aix?.decision
  );
  renderViolations(result.violations || []);
  els.safeResponse.textContent = result.output || result.raw_result?.safe_response || "";
  els.aixDetails.textContent = formatJson({
    aix: result.aix,
    candidate_aix: result.candidate_aix,
    candidate_gate: result.candidate_gate,
    audit_appended: payload.audit_appended,
  });
  els.auditRecord.textContent = formatJson(payload.audit_record || {});
}

async function loadGallery() {
  const response = await fetch("/playground/gallery");
  if (!response.ok) throw new Error(`Gallery request failed: HTTP ${response.status}`);
  const payload = await response.json();
  state.gallery = payload.adapters || [];
  renderAdapters();
  const requested = requestedAdapterId();
  const selected = state.gallery.find((entry) => entry.id === requested) || state.gallery[0];
  if (selected) selectAdapter(selected.id);
}

async function runCheck() {
  if (!state.selected) return;
  els.runCheck.disabled = true;
  els.runCheck.textContent = "Running...";
  try {
    const response = await fetch("/playground/check", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(buildRequest()),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || `Check failed: HTTP ${response.status}`);
    }
    renderResult(payload);
  } catch (error) {
    setMetric(els.gate, "error", "fail");
    els.safeResponse.textContent = error.message;
    els.auditRecord.textContent = "";
  } finally {
    els.runCheck.disabled = false;
    els.runCheck.textContent = "Run AANA Check";
  }
}

els.saveToken.addEventListener("click", () => {
  window.localStorage.setItem("aana.playground.token", els.token.value.trim());
});
els.filter.addEventListener("input", renderAdapters);
els.resetDemo.addEventListener("click", resetDemo);
els.runCheck.addEventListener("click", runCheck);

loadToken();
loadGallery().catch((error) => {
  els.adapterList.textContent = error.message;
});
