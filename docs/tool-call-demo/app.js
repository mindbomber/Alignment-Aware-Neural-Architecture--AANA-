const SAFE_DEMO_MODE = true;
const forbiddenExecutionActions = new Set(["send", "delete", "purchase", "deploy", "export"]);
const routeOrder = { accept: 0, ask: 1, defer: 2, refuse: 3 };
const authOrder = { none: 0, user_claimed: 1, authenticated: 2, validated: 3, confirmed: 4 };
const writePrefixes = [
  "add_",
  "append_",
  "approve_",
  "book_",
  "buy_",
  "cancel_",
  "commit_",
  "create_",
  "delete_",
  "deploy_",
  "disable_",
  "enable_",
  "export_",
  "freeze_",
  "grant_",
  "move_",
  "post_",
  "purchase_",
  "refund_",
  "remove_",
  "send_",
  "set_",
  "share_",
  "submit_",
  "transfer_",
  "unfreeze_",
  "update_",
  "write_"
];
const privateArgumentKeys = new Set([
  "account_id",
  "account_key",
  "card_id",
  "client_id",
  "customer_id",
  "employee_id",
  "email",
  "loan_id",
  "patient_id",
  "payment_id",
  "person_id",
  "student_id",
  "transaction_id",
  "user_id"
]);
const publicReadHints = ["public", "score", "weather", "docs", "documentation", "search_web", "web_search", "status"];

const examples = {
  private: {
    tool: {
      tool_name: "get_recent_transactions",
      arguments: { account_id: "acct_redacted", limit: 10 }
    },
    category: "private_read",
    auth: "authenticated",
    risk: "finance",
    evidence: [
      {
        source_id: "auth.email.lookup",
        kind: "auth_event",
        trust_tier: "verified",
        redaction_status: "redacted",
        summary: "User identity was authenticated through email lookup."
      },
      {
        source_id: "policy.bank.transactions",
        kind: "policy",
        trust_tier: "verified",
        redaction_status: "public",
        summary: "Authenticated users may read their own transaction history."
      }
    ]
  },
  write: {
    tool: {
      tool_name: "send_customer_email",
      arguments: { to: "customer@example.com", body: "Refund approved for account acct_redacted." }
    },
    category: "write",
    auth: "authenticated",
    risk: "customer_support",
    evidence: [
      {
        source_id: "auth.session",
        kind: "auth_event",
        trust_tier: "verified",
        redaction_status: "redacted",
        summary: "User is authenticated, but explicit confirmation is missing."
      }
    ]
  },
  public: {
    tool: {
      tool_name: "get_public_score",
      arguments: { game_id: "GAME-123" }
    },
    category: "public_read",
    auth: "none",
    risk: "public_information",
    evidence: [
      {
        source_id: "policy.public_scores",
        kind: "policy",
        trust_tier: "verified",
        redaction_status: "public",
        summary: "Game scores are public information."
      }
    ]
  }
};

const el = {
  toolJson: document.querySelector("#tool-json"),
  evidenceJson: document.querySelector("#evidence-json"),
  category: document.querySelector("#tool-category"),
  auth: document.querySelector("#authorization-state"),
  risk: document.querySelector("#risk-domain"),
  route: document.querySelector("#runtime-route"),
  gate: document.querySelector("#gate-decision"),
  action: document.querySelector("#recommended-action"),
  aix: document.querySelector("#aix-score"),
  gateCard: document.querySelector("#gate-card"),
  actionCard: document.querySelector("#action-card"),
  blockers: document.querySelector("#blockers"),
  reasons: document.querySelector("#reasons"),
  eventOutput: document.querySelector("#event-output"),
  resultOutput: document.querySelector("#result-output")
};

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function parseJson(text, fallback) {
  const trimmed = text.trim();
  if (!trimmed) return fallback;
  return JSON.parse(trimmed);
}

function toolNameFrom(raw) {
  return raw.tool_name || raw.name || raw.tool || raw.function?.name || "unknown_tool";
}

function argsFrom(raw) {
  if (raw.arguments && typeof raw.arguments === "object") return raw.arguments;
  if (raw.args && typeof raw.args === "object") return raw.args;
  if (raw.function?.arguments) {
    return typeof raw.function.arguments === "string" ? JSON.parse(raw.function.arguments) : raw.function.arguments;
  }
  if (raw.proposed_arguments && typeof raw.proposed_arguments === "object") return raw.proposed_arguments;
  return {};
}

function inferCategory(toolName, args) {
  const selected = el.category.value;
  if (selected !== "auto") return selected;
  const name = toolName.toLowerCase();
  if (writePrefixes.some((prefix) => name.startsWith(prefix))) return "write";
  if (Object.keys(args).some((key) => privateArgumentKeys.has(key))) return "private_read";
  if (["get_", "list_", "read_", "search_", "fetch_", "find_"].some((prefix) => name.startsWith(prefix))) {
    return publicReadHints.some((hint) => name.includes(hint)) ? "public_read" : "private_read";
  }
  return publicReadHints.some((hint) => name.includes(hint)) ? "public_read" : "unknown";
}

function inferRisk(toolName) {
  if (el.risk.value !== "auto") return el.risk.value;
  const name = toolName.toLowerCase();
  if (["deploy", "ci", "kubernetes", "server", "secret", "env", "repo"].some((hint) => name.includes(hint))) return "devops";
  if (["account", "card", "loan", "payment", "refund", "transfer", "invoice"].some((hint) => name.includes(hint))) return "finance";
  if (["employee", "candidate", "payroll", "hr_"].some((hint) => name.includes(hint))) return "hr";
  if (["legal", "contract", "case"].some((hint) => name.includes(hint))) return "legal";
  if (["patient", "medical", "drug", "trial", "pharma"].some((hint) => name.includes(hint))) return "pharma";
  if (publicReadHints.some((hint) => name.includes(hint))) return "public_information";
  return "unknown";
}

function stricterRoute(left, right) {
  return routeOrder[left] >= routeOrder[right] ? left : right;
}

function aixForRoute(route, hardBlockers) {
  const scores = { accept: 0.95, ask: 0.72, defer: 0.45, refuse: 0.15 };
  return {
    aix_version: "0.1",
    score: scores[route],
    components: {
      P: scores[route],
      F: route === "accept" ? 1.0 : 0.75,
      C: scores[route]
    },
    decision: route,
    hard_blockers: hardBlockers
  };
}

function hasMissingAuthorizationEvidence(refs) {
  return refs.some((ref) => {
    const sourceId = String(ref.source_id || "");
    const kind = String(ref.kind || "");
    const summary = String(ref.summary || "").toLowerCase();
    return (
      sourceId.startsWith("counterfactual.missing_authorization") ||
      (kind === "system_state" && summary.includes("missing authorization")) ||
      (kind === "system_state" && summary.includes("removes verified authorization"))
    );
  });
}

function validateEvent(event) {
  const errors = [];
  if (event.schema_version !== "aana.agent_tool_precheck.v1") errors.push({ path: "schema_version", message: "Unsupported schema_version." });
  if (!event.tool_name) errors.push({ path: "tool_name", message: "tool_name is required." });
  if (event.tool_category === "write" && event.recommended_route === "accept" && !["validated", "confirmed"].includes(event.authorization_state)) {
    errors.push({ path: "authorization_state", message: "write accept requires validated or confirmed authorization." });
  }
  if (event.tool_category === "private_read" && event.recommended_route === "accept" && !["authenticated", "validated", "confirmed"].includes(event.authorization_state)) {
    errors.push({ path: "authorization_state", message: "private_read accept requires authenticated, validated, or confirmed authorization." });
  }
  if (event.tool_category === "unknown" && event.recommended_route === "accept") {
    errors.push({ path: "recommended_route", message: "unknown tools cannot be accepted." });
  }
  return errors;
}

function gateEvent(event) {
  if (!SAFE_DEMO_MODE) {
    throw new Error("Public demo safety mode must remain enabled.");
  }
  const validationErrors = validateEvent(event);
  if (validationErrors.length) {
    const route = "refuse";
    const hardBlockers = ["schema_validation_failed"];
    return {
      contract_version: "aana.agent_tool_precheck.v1",
      tool_name: event.tool_name,
      gate_decision: "fail",
      recommended_action: route,
      candidate_gate: "fail",
      aix: aixForRoute(route, hardBlockers),
      hard_blockers: hardBlockers,
      reasons: ["event_failed_schema_validation"],
      validation_errors: validationErrors
    };
  }

  const reasons = [];
  const hardBlockers = [];
  let aanaRoute;

  if (event.tool_category === "public_read") {
    aanaRoute = "accept";
    reasons.push("public_read_allowed_without_identity_auth");
  } else if (event.tool_category === "private_read") {
    if (authOrder[event.authorization_state] >= authOrder.authenticated) {
      aanaRoute = "accept";
      reasons.push("private_read_has_authenticated_context");
    } else if (event.authorization_state === "user_claimed") {
      aanaRoute = "ask";
      reasons.push("private_read_needs_verified_authentication");
      hardBlockers.push("private_read_not_authenticated");
    } else {
      aanaRoute = "defer";
      reasons.push("private_read_missing_authorization_context");
      hardBlockers.push("private_read_not_authenticated");
    }
  } else if (event.tool_category === "write") {
    if (authOrder[event.authorization_state] >= authOrder.confirmed) {
      aanaRoute = "accept";
      reasons.push("write_has_explicit_confirmation");
    } else if (event.authorization_state === "validated") {
      aanaRoute = "ask";
      reasons.push("write_validated_but_needs_explicit_confirmation");
      hardBlockers.push("write_missing_explicit_confirmation");
    } else if (event.authorization_state === "authenticated" || event.authorization_state === "user_claimed") {
      aanaRoute = "ask";
      reasons.push("write_needs_validation_and_confirmation");
      hardBlockers.push("write_missing_validation_or_confirmation");
    } else {
      aanaRoute = "defer";
      reasons.push("write_missing_authorization_context");
      hardBlockers.push("write_missing_authorization");
    }
  } else {
    aanaRoute = "defer";
    reasons.push("unknown_tool_category_requires_review");
    hardBlockers.push("unknown_tool_category");
  }

  if (hasMissingAuthorizationEvidence(event.evidence_refs)) {
    aanaRoute = stricterRoute(aanaRoute, "defer");
    reasons.push("evidence_declares_missing_authorization");
    hardBlockers.push("evidence_missing_authorization");
  }

  if (["private_read", "write", "unknown"].includes(event.tool_category) && event.evidence_refs.length === 0) {
    aanaRoute = stricterRoute(aanaRoute, "defer");
    reasons.push("missing_evidence_refs_for_consequential_tool");
    hardBlockers.push("missing_evidence_refs");
  }

  const finalRoute = stricterRoute(aanaRoute, event.recommended_route);
  if (finalRoute !== aanaRoute) reasons.push(`runtime_recommended_stricter_route:${event.recommended_route}`);
  if (event.recommended_route === "refuse" && !hardBlockers.includes("runtime_refusal")) hardBlockers.push("runtime_refusal");

  return {
    contract_version: "aana.agent_tool_precheck.v1",
    demo_mode: "safe_static_only",
    real_execution: false,
    forbidden_execution_actions: Array.from(forbiddenExecutionActions),
    tool_name: event.tool_name,
    tool_category: event.tool_category,
    authorization_state: event.authorization_state,
    risk_domain: event.risk_domain,
    gate_decision: finalRoute === "accept" && hardBlockers.length === 0 ? "pass" : "fail",
    recommended_action: finalRoute,
    candidate_gate: aanaRoute === "accept" && hardBlockers.length === 0 ? "pass" : "fail",
    aana_route: aanaRoute,
    runtime_recommended_route: event.recommended_route,
    aix: aixForRoute(finalRoute, hardBlockers),
    hard_blockers: hardBlockers,
    reasons,
    evidence_ref_count: event.evidence_refs.length
  };
}

function normalizeEvent() {
  const raw = parseJson(el.toolJson.value, {});
  if (raw.schema_version === "aana.agent_tool_precheck.v1") return raw;

  const toolName = toolNameFrom(raw);
  const args = argsFrom(raw);
  const refs = parseJson(el.evidenceJson.value, []);
  return {
    schema_version: "aana.agent_tool_precheck.v1",
    request_id: `demo-${Date.now()}`,
    agent_id: "public_tool_call_demo",
    tool_name: toolName,
    tool_category: inferCategory(toolName, args),
    authorization_state: el.auth.value,
    evidence_refs: refs,
    risk_domain: inferRisk(toolName),
    proposed_arguments: args,
    recommended_route: el.route.value
  };
}

function chips(target, values) {
  target.innerHTML = "";
  const list = values && values.length ? values : ["none"];
  for (const value of list) {
    const chip = document.createElement("span");
    chip.className = `chip${value === "none" ? " empty" : ""}`;
    chip.textContent = value;
    target.append(chip);
  }
}

function setTone(card, value) {
  if (value === "pass" || value === "accept") card.dataset.tone = "pass";
  else if (value === "ask" || value === "defer") card.dataset.tone = "warn";
  else if (value === "fail" || value === "refuse") card.dataset.tone = "fail";
  else card.dataset.tone = "idle";
}

function render(event, result) {
  el.gate.textContent = result.gate_decision;
  el.action.textContent = result.recommended_action;
  el.aix.textContent = result.aix ? result.aix.score.toFixed(2) : "-";
  setTone(el.gateCard, result.gate_decision);
  setTone(el.actionCard, result.recommended_action);
  chips(el.blockers, result.hard_blockers || []);
  chips(el.reasons, result.reasons || []);
  el.eventOutput.textContent = pretty(event);
  el.resultOutput.textContent = pretty(result);
}

function renderError(error) {
  const result = {
    gate_decision: "fail",
    recommended_action: "refuse",
    aix: aixForRoute("refuse", ["invalid_json"]),
    hard_blockers: ["invalid_json"],
    reasons: [error.message]
  };
  render({}, result);
}

function runGate() {
  try {
    const event = normalizeEvent();
    const result = gateEvent(event);
    render(event, result);
  } catch (error) {
    renderError(error);
  }
}

function loadExample(kind) {
  const item = examples[kind];
  el.toolJson.value = pretty(item.tool);
  el.evidenceJson.value = pretty(item.evidence);
  el.category.value = item.category;
  el.auth.value = item.auth;
  el.risk.value = item.risk;
  el.route.value = "accept";
  runGate();
}

document.querySelector("#run-gate").addEventListener("click", runGate);
document.querySelector("#load-private").addEventListener("click", () => loadExample("private"));
document.querySelector("#load-write").addEventListener("click", () => loadExample("write"));
document.querySelector("#load-public").addEventListener("click", () => loadExample("public"));

loadExample("private");
