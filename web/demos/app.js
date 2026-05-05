const DEFAULT_ALLOWED = ["accept", "revise", "retrieve", "ask", "defer", "refuse"];
const ACTION_PRESETS = {
  all: DEFAULT_ALLOWED,
  "no-accept": ["revise", "retrieve", "ask", "defer", "refuse"],
  "human-review": ["ask", "defer", "refuse"],
};

const state = {
  demos: [],
  selected: null,
};

const els = {
  token: document.getElementById("token"),
  saveToken: document.getElementById("save-token"),
  tabs: Array.from(document.querySelectorAll(".demo-tab")),
  title: document.getElementById("demo-title"),
  subtitle: document.getElementById("demo-subtitle"),
  candidateLabel: document.getElementById("candidate-label"),
  candidate: document.getElementById("candidate"),
  facts: document.getElementById("facts"),
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
  const saved = window.localStorage.getItem("aana.demos.token");
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

function fieldInput(field) {
  const wrapper = document.createElement("div");
  wrapper.className = "fact";
  const label = document.createElement("label");
  label.htmlFor = `fact-${field.id}`;
  label.textContent = field.label;
  let input;
  if (field.type === "textarea") {
    input = document.createElement("textarea");
    input.rows = field.rows || 3;
  } else if (field.type === "select") {
    input = document.createElement("select");
    for (const option of field.options || []) {
      const item = document.createElement("option");
      item.value = option;
      item.textContent = option;
      input.appendChild(item);
    }
  } else {
    input = document.createElement("input");
    input.type = field.type || "text";
  }
  input.id = `fact-${field.id}`;
  input.dataset.fieldId = field.id;
  input.value = field.value || "";
  wrapper.append(label, input);
  return wrapper;
}

function factValue(id) {
  const input = els.facts.querySelector(`[data-field-id="${id}"]`);
  return input ? input.value : "";
}

function evidenceFromFacts() {
  const demo = state.selected;
  return (demo.evidence_template || []).map((template) => ({
    source_id: template.source_id,
    trust_tier: template.trust_tier || "verified",
    redaction_status: template.redaction_status || "synthetic",
    text: template.text.replace(/\{\{([^}]+)\}\}/g, (_, key) => factValue(key.trim())),
  }));
}

function buildRequest() {
  const demo = state.selected;
  const evidence = evidenceFromFacts();
  for (const line of splitLines(els.evidence.value)) {
    evidence.push({
      source_id: "user-demo-note",
      trust_tier: "operator_supplied",
      redaction_status: "local_demo",
      text: line,
    });
  }
  return {
    contract_version: "0.1",
    workflow_id: `local-demo-${demo.id}`,
    adapter: demo.adapter_id,
    request: demo.request,
    candidate: els.candidate.value,
    evidence,
    constraints: splitLines(els.constraints.value),
    allowed_actions: selectedAllowedActions(),
    metadata: {
      surface: "aana_local_desktop_browser_demo",
      demo_id: demo.id,
      action_family: demo.action_family,
    },
  };
}

function selectDemo(demoId) {
  const demo = state.demos.find((item) => item.id === demoId);
  if (!demo) return;
  state.selected = demo;
  for (const tab of els.tabs) {
    tab.classList.toggle("active", tab.dataset.demo === demoId);
  }
  resetDemo();
}

function resetDemo() {
  const demo = state.selected;
  if (!demo) return;
  els.title.textContent = demo.title;
  els.subtitle.textContent = demo.subtitle;
  els.candidateLabel.textContent = demo.candidate_label || "Draft action";
  els.candidate.value = demo.candidate;
  els.evidence.value = (demo.extra_evidence || []).join("\n");
  els.constraints.value = (demo.constraints || []).join("\n");
  els.allowedAction.value = demo.allowed_action_preset || "all";
  els.facts.innerHTML = "";
  for (const field of demo.fields || []) {
    els.facts.appendChild(fieldInput(field));
  }
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

async function loadDemos() {
  const response = await fetch("/demos/scenarios");
  if (!response.ok) throw new Error(`Demo request failed: HTTP ${response.status}`);
  const payload = await response.json();
  state.demos = payload.demos || [];
  selectDemo("email_send");
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
  window.localStorage.setItem("aana.demos.token", els.token.value.trim());
});
els.resetDemo.addEventListener("click", resetDemo);
els.runCheck.addEventListener("click", runCheck);
for (const tab of els.tabs) {
  tab.addEventListener("click", () => selectDemo(tab.dataset.demo));
}

loadToken();
loadDemos().catch((error) => {
  els.safeResponse.textContent = error.message;
});
