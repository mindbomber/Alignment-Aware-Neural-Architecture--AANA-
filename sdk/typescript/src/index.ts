export type AanaAction = "accept" | "revise" | "retrieve" | "ask" | "defer" | "refuse";
export type ToolPrecheckAction = "accept" | "ask" | "defer" | "refuse";
export type ToolCategory = "public_read" | "private_read" | "write" | "unknown";
export type AuthorizationState = "none" | "user_claimed" | "authenticated" | "validated" | "confirmed";
export type RiskDomain =
  | "devops"
  | "finance"
  | "education"
  | "hr"
  | "legal"
  | "pharma"
  | "healthcare"
  | "commerce"
  | "customer_support"
  | "security"
  | "research"
  | "personal_productivity"
  | "public_information"
  | "unknown";

export const TOOL_PRECHECK_SCHEMA_VERSION = "aana.agent_tool_precheck.v1" as const;
export const PUBLIC_ARCHITECTURE_CLAIM = "AANA is an architecture for making agents more auditable, safer, more grounded, and more controllable." as const;
export const ROUTE_TABLE: Record<AanaAction, { description: string; execution_allowed: boolean; next_step: string }> = {
  accept: {
    description: "Proceed only within the checked scope.",
    execution_allowed: true,
    next_step: "execute_checked_action"
  },
  revise: {
    description: "Revise the candidate output or action, then recheck before execution.",
    execution_allowed: false,
    next_step: "revise_then_recheck"
  },
  retrieve: {
    description: "Retrieve missing grounding or policy evidence, then recheck before execution.",
    execution_allowed: false,
    next_step: "retrieve_evidence_then_recheck"
  },
  ask: {
    description: "Ask the user or runtime for missing information, authorization, or confirmation.",
    execution_allowed: false,
    next_step: "ask_then_recheck"
  },
  defer: {
    description: "Route to stronger evidence, a domain owner, review queue, or human reviewer.",
    execution_allowed: false,
    next_step: "defer_to_review"
  },
  refuse: {
    description: "Do not execute because a hard blocker prevents safe action.",
    execution_allowed: false,
    next_step: "refuse_action"
  }
} as const;

export function routeAllowsExecution(route: AanaAction | string | undefined): boolean {
  return route === "accept";
}

export interface EvidenceObject {
  text: string;
  source_id?: string;
  retrieved_at?: string;
  trust_tier?: string;
  redaction_status?: string;
  metadata?: Record<string, unknown>;
  raw_record_id?: string;
  [key: string]: unknown;
}

export type EvidenceInput = string | EvidenceObject;

export interface WorkflowRequest {
  contract_version: "0.1";
  adapter: string;
  request: string;
  candidate?: string | null;
  evidence?: EvidenceInput[];
  constraints?: string[];
  allowed_actions?: AanaAction[];
  metadata?: Record<string, unknown>;
  workflow_id?: string;
}

export interface AgentEvent {
  event_version: "0.1";
  user_request: string;
  agent?: string;
  event_id?: string;
  adapter_id?: string;
  workflow?: string;
  candidate_action?: string;
  candidate_answer?: string;
  draft_response?: string;
  available_evidence?: EvidenceInput[];
  allowed_actions?: AanaAction[];
  metadata?: Record<string, unknown>;
}

export interface ToolEvidenceRef {
  source_id: string;
  kind:
    | "user_message"
    | "assistant_message"
    | "tool_result"
    | "policy"
    | "auth_event"
    | "approval"
    | "system_state"
    | "audit_record"
    | "other";
  trust_tier?: "verified" | "runtime" | "user_claimed" | "unverified" | "unknown";
  redaction_status?: "public" | "redacted" | "sensitive" | "unknown";
  freshness?: {
    status: "fresh" | "stale" | "unknown";
    checked_at?: string;
    max_age_hours?: number;
    age_hours?: number;
    source?: string;
  };
  provenance?: string;
  summary?: string;
}

export interface AuthorizationSubject {
  subject_type?: "user" | "account" | "client" | "employee" | "student" | "patient" | "case" | "service" | "unknown";
  subject_ref?: string;
}

export interface ToolPrecheckEvent {
  schema_version: typeof TOOL_PRECHECK_SCHEMA_VERSION;
  tool_name: string;
  tool_category: ToolCategory;
  authorization_state: AuthorizationState;
  evidence_refs: ToolEvidenceRef[];
  risk_domain: RiskDomain;
  proposed_arguments: Record<string, unknown>;
  recommended_route: ToolPrecheckAction;
  request_id?: string;
  agent_id?: string;
  user_intent?: string;
  authorization_subject?: AuthorizationSubject;
}

export interface ToolPrecheckResult {
  contract_version: typeof TOOL_PRECHECK_SCHEMA_VERSION;
  tool_name?: string;
  tool_category?: ToolCategory;
  authorization_state?: AuthorizationState;
  risk_domain?: RiskDomain;
  gate_decision: "pass" | "fail";
  recommended_action: ToolPrecheckAction;
  candidate_gate: "pass" | "fail";
  aana_route?: ToolPrecheckAction;
  runtime_recommended_route?: ToolPrecheckAction;
  aix: {
    aix_version: string;
    score: number;
    components: Record<string, number>;
    decision: ToolPrecheckAction;
    hard_blockers: string[];
  };
  hard_blockers: string[];
  reasons: string[];
  evidence_ref_count?: number;
  validation_errors?: Array<{ path: string; message: string }>;
  architecture_decision?: ArchitectureDecision;
  execution_policy?: ExecutionPolicy;
}

export interface ArchitectureDecision {
  architecture_claim: typeof PUBLIC_ARCHITECTURE_CLAIM;
  route: ToolPrecheckAction;
  gate_decision?: "pass" | "fail";
  candidate_gate?: "pass" | "fail";
  aix_score?: number;
  aix_decision?: ToolPrecheckAction;
  hard_blockers: string[];
  evidence_refs: {
    used: string[];
    missing: string[];
  };
  authorization_state: AuthorizationState | "not_declared";
  tool_name?: string;
  tool_category?: ToolCategory;
  risk_domain?: RiskDomain;
  correction_recovery_suggestion: string;
  audit_safe_log_event: Record<string, unknown>;
}

export interface ExecutionPolicy {
  mode: "enforce" | "shadow";
  aana_allows_execution: boolean;
  execution_allowed: boolean;
  fail_closed: boolean;
  reason: string;
  required_route: "accept";
  route_table: typeof ROUTE_TABLE;
  observed: {
    gate_decision?: "pass" | "fail";
    recommended_action?: ToolPrecheckAction;
    architecture_route?: ToolPrecheckAction;
    hard_blocker_count: number;
    validation_error_count: number;
  };
}

export interface AanaMiddlewareError {
  error_type: "aana_tool_execution_blocked";
  code: string;
  message: string;
  route: ToolPrecheckAction;
  tool_name?: string;
  tool_category?: ToolCategory;
  risk_domain?: RiskDomain;
  hard_blockers: string[];
  recovery_suggestion: string;
  execution_policy: ExecutionPolicy;
  audit_safe_log_event?: Record<string, unknown>;
}

export interface AanaGateResult {
  event: ToolPrecheckEvent;
  result: ToolPrecheckResult;
  allowed: boolean;
  execution_allowed: boolean;
  execution_policy: ExecutionPolicy;
  error?: AanaMiddlewareError;
}

export interface AanaClientOptions {
  baseUrl: string;
  token?: string;
  timeoutMs?: number;
  shadowMode?: boolean;
  fetchImpl?: typeof fetch;
}

export interface AanaClientResult {
  [key: string]: unknown;
}

export const FAMILY_ADAPTER_ALIASES = {
  support: {
    draft: "support_reply",
    crm: "crm_support_reply",
    email: "email_send_guardrail",
    ticket: "ticket_update_checker",
    billing: "invoice_billing_reply"
  },
  enterprise: {
    access: "access_permission_change",
    code_review: "code_change_review",
    crm_support: "crm_support_reply",
    data_export: "data_export_guardrail",
    deployment: "deployment_readiness",
    email: "email_send_guardrail",
    incident: "incident_response_update",
    ticket: "ticket_update_checker"
  },
  personal_productivity: {
    booking: "booking_purchase_guardrail",
    calendar: "calendar_scheduling",
    email: "email_send_guardrail",
    file: "file_operation_guardrail",
    meeting: "meeting_summary_checker",
    publication: "publication_check",
    research: "research_answer_grounding"
  },
  government_civic: {
    casework: "casework_response_checker",
    foia: "foia_public_records_response_checker",
    grant: "grant_application_review",
    insurance: "insurance_claim_triage",
    policy_memo: "policy_memo_grounding",
    procurement: "procurement_vendor_risk",
    publication: "publication_check",
    records: "public_records_privacy_redaction"
  }
} as const;

export function normalizeEvidence(
  evidence?: EvidenceInput | EvidenceInput[],
  defaults: Partial<EvidenceObject> = {}
): EvidenceInput[] {
  if (evidence === undefined || evidence === null) return [];
  const items = Array.isArray(evidence) ? evidence : [evidence];
  return items.map((item) => {
    if (typeof item === "string") {
      if (!item.trim()) throw new Error("Evidence text must be non-empty.");
      if (defaults.source_id) {
        return {
          source_id: defaults.source_id,
          retrieved_at: defaults.retrieved_at,
          trust_tier: defaults.trust_tier ?? "verified",
          redaction_status: defaults.redaction_status ?? "redacted",
          metadata: defaults.metadata,
          raw_record_id: defaults.raw_record_id,
          text: item
        };
      }
      return item;
    }
    if (!item || typeof item !== "object" || typeof item.text !== "string" || !item.text.trim()) {
      throw new Error("Structured evidence must include non-empty text.");
    }
    return {
      ...defaults,
      trust_tier: defaults.trust_tier ?? item.trust_tier ?? "verified",
      redaction_status: defaults.redaction_status ?? item.redaction_status ?? "redacted",
      ...item
    };
  });
}

export function evidenceObject(text: string, defaults: EvidenceObject & { source_id: string }): EvidenceObject {
  const [item] = normalizeEvidence(text, defaults);
  if (typeof item === "string") {
    throw new Error("evidenceObject requires a source_id and returns structured evidence.");
  }
  return item;
}

export function workflowRequest(input: {
  adapter: string;
  request: string;
  candidate?: string | null;
  evidence?: EvidenceInput | EvidenceInput[];
  constraints?: string | string[];
  allowedActions?: AanaAction[];
  metadata?: Record<string, unknown>;
  workflowId?: string;
}): WorkflowRequest {
  return {
    contract_version: "0.1",
    adapter: input.adapter,
    request: input.request,
    candidate: input.candidate,
    evidence: normalizeEvidence(input.evidence),
    constraints: input.constraints === undefined ? [] : Array.isArray(input.constraints) ? input.constraints : [input.constraints],
    allowed_actions: input.allowedActions,
    metadata: input.metadata,
    workflow_id: input.workflowId
  };
}

export function familyWorkflowRequest(
  family: string,
  input: Parameters<typeof workflowRequest>[0]
): WorkflowRequest {
  return workflowRequest({
    ...input,
    metadata: { ...(input.metadata ?? {}), aana_family: family }
  });
}

export function agentEvent(input: {
  userRequest: string;
  adapterId?: string;
  workflow?: string;
  candidateAction?: string;
  candidateAnswer?: string;
  draftResponse?: string;
  availableEvidence?: EvidenceInput | EvidenceInput[];
  allowedActions?: AanaAction[];
  metadata?: Record<string, unknown>;
  agent?: string;
  eventId?: string;
}): AgentEvent {
  if (!input.adapterId && !input.workflow) {
    throw new Error("Agent event requires adapterId or workflow.");
  }
  return {
    event_version: "0.1",
    event_id: input.eventId,
    agent: input.agent ?? "app",
    adapter_id: input.adapterId,
    workflow: input.workflow,
    user_request: input.userRequest,
    candidate_action: input.candidateAction,
    candidate_answer: input.candidateAnswer,
    draft_response: input.draftResponse,
    available_evidence: normalizeEvidence(input.availableEvidence),
    allowed_actions: input.allowedActions,
    metadata: input.metadata
  };
}

export function toolEvidenceRef(input: ToolEvidenceRef): ToolEvidenceRef {
  if (!input.source_id?.trim()) throw new Error("Tool evidence ref requires a non-empty source_id.");
  if (!input.kind) throw new Error("Tool evidence ref requires a kind.");
  return {
    trust_tier: "unknown",
    redaction_status: "unknown",
    freshness: { status: input.trust_tier === "verified" || input.trust_tier === "runtime" ? "fresh" : "unknown" },
    provenance: "runtime",
    ...input
  };
}

export function toolPrecheckEvent(input: {
  toolName: string;
  toolCategory: ToolCategory;
  authorizationState: AuthorizationState;
  evidenceRefs: ToolEvidenceRef[];
  riskDomain: RiskDomain;
  proposedArguments: Record<string, unknown>;
  recommendedRoute?: ToolPrecheckAction;
  requestId?: string;
  agentId?: string;
  userIntent?: string;
  authorizationSubject?: AuthorizationSubject;
}): ToolPrecheckEvent {
  return {
    schema_version: TOOL_PRECHECK_SCHEMA_VERSION,
    request_id: input.requestId,
    agent_id: input.agentId,
    tool_name: input.toolName,
    tool_category: input.toolCategory,
    authorization_state: input.authorizationState,
    evidence_refs: input.evidenceRefs.map(toolEvidenceRef),
    risk_domain: input.riskDomain,
    proposed_arguments: { ...input.proposedArguments },
    recommended_route: input.recommendedRoute ?? "accept",
    user_intent: input.userIntent,
    authorization_subject: input.authorizationSubject
  };
}

const routeOrder: Record<ToolPrecheckAction, number> = { accept: 0, ask: 1, defer: 2, refuse: 3 };
export const AUTHORIZATION_STATES = ["none", "user_claimed", "authenticated", "validated", "confirmed"] as const;
export const AUTHORIZATION_STATE_TABLE: Record<AuthorizationState, {
  rank: number;
  privateReadAllowed: boolean;
  writeSchemaAcceptAllowed: boolean;
  writeExecutionAllowed: boolean;
}> = {
  none: { rank: 0, privateReadAllowed: false, writeSchemaAcceptAllowed: false, writeExecutionAllowed: false },
  user_claimed: { rank: 1, privateReadAllowed: false, writeSchemaAcceptAllowed: false, writeExecutionAllowed: false },
  authenticated: { rank: 2, privateReadAllowed: true, writeSchemaAcceptAllowed: false, writeExecutionAllowed: false },
  validated: { rank: 3, privateReadAllowed: true, writeSchemaAcceptAllowed: true, writeExecutionAllowed: false },
  confirmed: { rank: 4, privateReadAllowed: true, writeSchemaAcceptAllowed: true, writeExecutionAllowed: true }
};

function stricterRoute(left: ToolPrecheckAction, right: ToolPrecheckAction): ToolPrecheckAction {
  return routeOrder[left] >= routeOrder[right] ? left : right;
}

export function canonicalizeAuthorizationState(value: string | undefined | null): AuthorizationState {
  const normalized = (value ?? "").trim().toLowerCase().replace(/[-\s]+/g, "_");
  if ((AUTHORIZATION_STATES as readonly string[]).includes(normalized)) return normalized as AuthorizationState;
  const aliases: Record<string, AuthorizationState> = {
    "": "none",
    anonymous: "none",
    unauthenticated: "none",
    unauthorized: "none",
    unknown: "none",
    claimed: "user_claimed",
    requested: "user_claimed",
    user_requested: "user_claimed",
    logged_in: "authenticated",
    login: "authenticated",
    session: "authenticated",
    verified_identity: "authenticated",
    verified: "validated",
    eligible: "validated",
    policy_validated: "validated",
    ownership_validated: "validated",
    approved: "confirmed",
    confirmation: "confirmed",
    explicit_confirmation: "confirmed",
    user_confirmed: "confirmed"
  };
  return aliases[normalized] ?? "none";
}

export function authStateAtLeast(state: AuthorizationState, minimum: AuthorizationState): boolean {
  return AUTHORIZATION_STATE_TABLE[state].rank >= AUTHORIZATION_STATE_TABLE[minimum].rank;
}

export function privateReadAllowed(state: AuthorizationState): boolean {
  return AUTHORIZATION_STATE_TABLE[state].privateReadAllowed;
}

export function writeSchemaAcceptAllowed(state: AuthorizationState): boolean {
  return AUTHORIZATION_STATE_TABLE[state].writeSchemaAcceptAllowed;
}

export function writeExecutionAllowed(state: AuthorizationState): boolean {
  return AUTHORIZATION_STATE_TABLE[state].writeExecutionAllowed;
}

function aixForRoute(route: ToolPrecheckAction, hardBlockers: string[]): ToolPrecheckResult["aix"] {
  const scores: Record<ToolPrecheckAction, number> = { accept: 0.95, ask: 0.72, defer: 0.45, refuse: 0.15 };
  return {
    aix_version: "0.1",
    score: scores[route],
    components: { P: scores[route], F: route === "accept" ? 1.0 : 0.75, C: scores[route] },
    decision: route,
    hard_blockers: hardBlockers
  };
}

function hasMissingAuthorizationEvidence(evidenceRefs: ToolEvidenceRef[]): boolean {
  return evidenceRefs.some((ref) => {
    const summary = (ref.summary ?? "").toLowerCase();
    return (
      ref.source_id.startsWith("counterfactual.missing_authorization") ||
      (ref.kind === "system_state" && summary.includes("missing authorization")) ||
      (ref.kind === "system_state" && summary.includes("removes verified authorization"))
    );
  });
}

function isIdentityBoundPublicRead(event: ToolPrecheckEvent): boolean {
  if (event.tool_category !== "public_read") return false;
  const name = event.tool_name.toLowerCase();
  const keys = Object.keys(event.proposed_arguments ?? {});
  const privateKeys = ["account_id", "card_id", "case_id", "client_id", "customer_id", "employee_id", "email", "invoice_id", "loan_id", "order_id", "patient_id", "payment_id", "profile_id", "student_id", "subscription_id", "ticket_id", "transaction_id", "user_id"];
  const privateHints = ["account", "booking", "cart", "client", "customer", "invoice", "order", "profile", "reservation", "subscription", "ticket", "transaction", "user"];
  return keys.some((key) => privateKeys.includes(key)) || privateHints.some((hint) => name.includes(hint));
}

function isHighRiskWrite(event: ToolPrecheckEvent): boolean {
  if (event.tool_category !== "write") return false;
  const name = event.tool_name.toLowerCase();
  const highRisk = ["delete", "transfer", "pay", "purchase", "reset", "send", "deploy", "grant", "revoke"];
  return highRisk.some((term) => name.includes(term)) || ["finance", "devops", "security", "legal", "pharma", "healthcare"].includes(event.risk_domain);
}

export function validateToolPrecheckEvent(event: ToolPrecheckEvent): { valid: boolean; errors: Array<{ path: string; message: string }> } {
  const errors: Array<{ path: string; message: string }> = [];
  if (event.schema_version !== TOOL_PRECHECK_SCHEMA_VERSION) errors.push({ path: "schema_version", message: "Unsupported schema_version." });
  if (!event.tool_name?.trim()) errors.push({ path: "tool_name", message: "tool_name must be non-empty." });
  if (!["public_read", "private_read", "write", "unknown"].includes(event.tool_category)) errors.push({ path: "tool_category", message: "Unsupported tool_category." });
  if (!(AUTHORIZATION_STATES as readonly string[]).includes(event.authorization_state)) errors.push({ path: "authorization_state", message: "Unsupported authorization_state." });
  if (!Array.isArray(event.evidence_refs)) errors.push({ path: "evidence_refs", message: "evidence_refs must be an array." });
  if (!["accept", "ask", "defer", "refuse"].includes(event.recommended_route)) errors.push({ path: "recommended_route", message: "Unsupported recommended_route." });
  if (event.tool_category === "write" && event.recommended_route === "accept" && !writeSchemaAcceptAllowed(event.authorization_state)) {
    errors.push({ path: "authorization_state", message: "write accept requires validated or confirmed authorization." });
  }
  if (event.tool_category === "private_read" && event.recommended_route === "accept" && !privateReadAllowed(event.authorization_state)) {
    errors.push({ path: "authorization_state", message: "private_read accept requires authenticated, validated, or confirmed authorization." });
  }
  if (event.tool_category === "unknown" && event.recommended_route === "accept") {
    errors.push({ path: "recommended_route", message: "unknown tools cannot be accepted." });
  }
  return { valid: errors.length === 0, errors };
}

export function checkToolPrecheck(event: ToolPrecheckEvent): ToolPrecheckResult {
  const validation = validateToolPrecheckEvent(event);
  if (!validation.valid) {
    const route: ToolPrecheckAction = "refuse";
    const hardBlockers = ["schema_validation_failed"];
    return {
      contract_version: TOOL_PRECHECK_SCHEMA_VERSION,
      tool_name: event.tool_name,
      gate_decision: "fail",
      recommended_action: route,
      candidate_gate: "fail",
      aix: aixForRoute(route, hardBlockers),
      hard_blockers: hardBlockers,
      reasons: ["event_failed_schema_validation"],
      validation_errors: validation.errors
    };
  }

  const reasons: string[] = [];
  const hardBlockers: string[] = [];
  let aanaRoute: ToolPrecheckAction;
  const effectiveCategory = isIdentityBoundPublicRead(event) ? "private_read" : event.tool_category;
  if (effectiveCategory !== event.tool_category) {
    reasons.push("public_read_reclassified_identity_bound_private_read");
    hardBlockers.push("public_read_identity_bound_misclassified");
  }
  if (effectiveCategory === "public_read") {
    aanaRoute = "accept";
    reasons.push("public_read_allowed_without_identity_auth");
  } else if (effectiveCategory === "private_read") {
    if (privateReadAllowed(event.authorization_state)) {
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
    if (isHighRiskWrite(event) && !writeExecutionAllowed(event.authorization_state)) {
      aanaRoute = authStateAtLeast(event.authorization_state, "user_claimed") ? "ask" : "defer";
      reasons.push("high_risk_write_requires_explicit_confirmation");
      hardBlockers.push("high_risk_write_missing_explicit_confirmation", "write_missing_explicit_confirmation");
      if (event.authorization_state === "user_claimed" || event.authorization_state === "authenticated") hardBlockers.push("write_missing_validation_or_confirmation");
    } else if (writeExecutionAllowed(event.authorization_state)) {
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
  const candidateGate = aanaRoute === "accept" && hardBlockers.length === 0 ? "pass" : "fail";
  const gateDecision = finalRoute === "accept" && hardBlockers.length === 0 ? "pass" : "fail";
  return {
    contract_version: TOOL_PRECHECK_SCHEMA_VERSION,
    tool_name: event.tool_name,
    tool_category: event.tool_category,
    authorization_state: event.authorization_state,
    risk_domain: event.risk_domain,
    gate_decision: gateDecision,
    recommended_action: finalRoute,
    candidate_gate: candidateGate,
    aana_route: aanaRoute,
    runtime_recommended_route: event.recommended_route,
    aix: aixForRoute(finalRoute, hardBlockers),
    hard_blockers: hardBlockers,
    reasons,
    evidence_ref_count: event.evidence_refs.length
  };
}

function correctionRecoverySuggestion(route: ToolPrecheckAction): string {
  if (route === "accept") return `${ROUTE_TABLE.accept.description} Append the audit-safe decision event.`;
  if (route === "ask") return "Ask the user or runtime for the missing authorization, confirmation, or evidence before execution.";
  if (route === "defer") return "Defer to stronger evidence retrieval, a domain owner, or human review before execution.";
  return "Refuse the proposed action because a hard blocker prevents safe execution.";
}

export function architectureDecision(result: ToolPrecheckResult, event: ToolPrecheckEvent): ArchitectureDecision {
  const blockers = result.hard_blockers.length ? result.hard_blockers : result.aix.hard_blockers;
  return {
    architecture_claim: PUBLIC_ARCHITECTURE_CLAIM,
    route: result.recommended_action,
    gate_decision: result.gate_decision,
    candidate_gate: result.candidate_gate,
    aix_score: result.aix.score,
    aix_decision: result.aix.decision,
    hard_blockers: blockers,
    evidence_refs: {
      used: event.evidence_refs.map((ref) => ref.source_id),
      missing: blockers.filter((item) => /missing|evidence|authorization|citation|source/.test(item))
    },
    authorization_state: event.authorization_state ?? "not_declared",
    tool_name: event.tool_name,
    tool_category: event.tool_category,
    risk_domain: event.risk_domain,
    correction_recovery_suggestion: correctionRecoverySuggestion(result.recommended_action),
    audit_safe_log_event: {
      gate_decision: result.gate_decision,
      recommended_action: result.recommended_action,
      aix: {
        score: result.aix.score,
        decision: result.aix.decision,
        hard_blockers: result.aix.hard_blockers
      },
      hard_blockers: blockers
    }
  };
}

export function withArchitectureDecision(result: ToolPrecheckResult, event: ToolPrecheckEvent): ToolPrecheckResult {
  const enriched = { ...result, architecture_decision: architectureDecision(result, event) };
  return { ...enriched, execution_policy: executionPolicy(enriched) };
}

export function checkToolCall(event: ToolPrecheckEvent): ToolPrecheckResult {
  return withArchitectureDecision(checkToolPrecheck(event), event);
}

export const gateAction = checkToolCall;

export function shouldExecuteTool(result: ToolPrecheckResult): boolean {
  return executionPolicy(result, "enforce").aana_allows_execution;
}

export function executionPolicy(result: ToolPrecheckResult, mode?: "enforce" | "shadow"): ExecutionPolicy {
  const requestedMode = mode ?? ((result as { shadow_mode?: boolean; execution_mode?: string }).shadow_mode || (result as { execution_mode?: string }).execution_mode === "shadow" ? "shadow" : "enforce");
  const architectureRoute = result.architecture_decision?.route ?? result.recommended_action;
  const hardBlockerCount = (result.hard_blockers ?? []).length + (result.aix?.hard_blockers ?? []).length + (result.architecture_decision?.hard_blockers ?? []).length;
  const validationErrorCount = (result.validation_errors ?? []).length;
  const aanaAllows = result.gate_decision === "pass" && result.recommended_action === "accept" && routeAllowsExecution(architectureRoute) && hardBlockerCount === 0 && validationErrorCount === 0;
  const executionAllowed = requestedMode === "enforce" ? aanaAllows : true;
  const reason = validationErrorCount > 0
    ? "schema_or_contract_validation_failed"
    : hardBlockerCount > 0
      ? "hard_blockers_present"
      : !aanaAllows
        ? "route_not_accept"
        : requestedMode === "shadow"
          ? "shadow_mode_observe_only"
          : "enforcement_accept";
  return {
    mode: requestedMode,
    aana_allows_execution: aanaAllows,
    execution_allowed: executionAllowed,
    fail_closed: !aanaAllows,
    reason,
    required_route: "accept",
    route_table: ROUTE_TABLE,
    observed: {
      gate_decision: result.gate_decision,
      recommended_action: result.recommended_action,
      architecture_route: architectureRoute,
      hard_blocker_count: hardBlockerCount,
      validation_error_count: validationErrorCount
    }
  };
}

export class AanaToolExecutionBlocked extends Error {
  readonly result: ToolPrecheckResult;
  readonly event: ToolPrecheckEvent;
  readonly error: AanaMiddlewareError;

  constructor(result: ToolPrecheckResult, event: ToolPrecheckEvent, error?: AanaMiddlewareError) {
    const blocked = error ?? middlewareError(result, event, executionPolicy(result));
    super(blocked.message);
    this.name = "AanaToolExecutionBlocked";
    this.result = result;
    this.event = event;
    this.error = blocked;
  }
}

export function middlewareError(result: ToolPrecheckResult, event: ToolPrecheckEvent, policy: ExecutionPolicy = executionPolicy(result)): AanaMiddlewareError {
  const route = result.architecture_decision?.route ?? result.recommended_action ?? "refuse";
  const hardBlockers = Array.from(new Set([...(result.hard_blockers ?? []), ...(result.architecture_decision?.hard_blockers ?? [])]));
  const recovery = result.architecture_decision?.correction_recovery_suggestion
    ?? (route === "ask"
      ? "Ask for missing authorization or evidence before retrying."
      : route === "defer"
        ? "Defer to stronger evidence retrieval, a domain owner, or human review before execution."
        : "Refuse the proposed action because a hard blocker prevents safe execution.");
  return {
    error_type: "aana_tool_execution_blocked",
    code: policy.reason || "aana_execution_blocked",
    message: `AANA blocked tool call ${event.tool_name}: route=${route}`,
    route,
    tool_name: event.tool_name,
    tool_category: event.tool_category,
    risk_domain: event.risk_domain,
    hard_blockers: hardBlockers,
    recovery_suggestion: recovery,
    execution_policy: policy,
    audit_safe_log_event: result.architecture_decision?.audit_safe_log_event
  };
}

export function inferToolCategory(toolName: string, proposedArguments: Record<string, unknown> = {}, metadata: Record<string, unknown> = {}): ToolCategory {
  if (metadata.tool_category === "public_read" || metadata.tool_category === "private_read" || metadata.tool_category === "write" || metadata.tool_category === "unknown") {
    return metadata.tool_category;
  }
  const name = toolName.toLowerCase();
  const privateKeys = new Set(["account_id", "account_key", "card_id", "client_id", "customer_id", "employee_id", "email", "loan_id", "patient_id", "payment_id", "student_id", "transaction_id", "user_id"]);
  const writePrefixes = ["add_", "append_", "approve_", "book_", "buy_", "cancel_", "commit_", "create_", "delete_", "deploy_", "disable_", "enable_", "export_", "freeze_", "grant_", "move_", "post_", "purchase_", "refund_", "remove_", "send_", "set_", "share_", "submit_", "transfer_", "unfreeze_", "update_", "write_"];
  const publicHints = ["public", "score", "weather", "docs", "documentation", "search_web", "web_search", "status"];
  if (writePrefixes.some((prefix) => name.startsWith(prefix))) return "write";
  if (Object.keys(proposedArguments).some((key) => privateKeys.has(key))) return "private_read";
  if (["get_", "list_", "read_", "search_", "fetch_", "find_"].some((prefix) => name.startsWith(prefix))) {
    return publicHints.some((hint) => name.includes(hint)) ? "public_read" : "private_read";
  }
  return publicHints.some((hint) => name.includes(hint)) ? "public_read" : "unknown";
}

export function inferRiskDomain(toolName: string, metadata: Record<string, unknown> = {}): RiskDomain {
  if (typeof metadata.risk_domain === "string") return metadata.risk_domain as RiskDomain;
  const name = toolName.toLowerCase();
  if (["deploy", "ci", "kubernetes", "server", "secret", "env", "repo"].some((hint) => name.includes(hint))) return "devops";
  if (["account", "card", "loan", "payment", "refund", "transfer", "invoice"].some((hint) => name.includes(hint))) return "finance";
  if (["employee", "candidate", "payroll", "hr_"].some((hint) => name.includes(hint))) return "hr";
  if (["legal", "contract", "case"].some((hint) => name.includes(hint))) return "legal";
  if (["patient", "medical", "drug", "trial", "pharma"].some((hint) => name.includes(hint))) return "pharma";
  if (["public", "score", "weather", "docs", "documentation", "search_web", "web_search", "status"].some((hint) => name.includes(hint))) return "public_information";
  return "unknown";
}

export function buildPrecheckFromToolCall(input: {
  toolName: string;
  proposedArguments?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  evidenceRefs?: ToolEvidenceRef[];
  requestId?: string;
  agentId?: string;
  userIntent?: string;
  recommendedRoute?: ToolPrecheckAction;
}): ToolPrecheckEvent {
  const metadata = input.metadata ?? {};
  return toolPrecheckEvent({
    toolName: input.toolName,
    toolCategory: inferToolCategory(input.toolName, input.proposedArguments ?? {}, metadata),
    authorizationState: (metadata.authorization_state as AuthorizationState | undefined) ?? "none",
    evidenceRefs: input.evidenceRefs ?? (metadata.evidence_refs as ToolEvidenceRef[] | undefined) ?? [
      toolEvidenceRef({
        source_id: `runtime.tool.${input.toolName}`,
        kind: "policy",
        trust_tier: "runtime",
        redaction_status: "redacted",
        summary: "Runtime provided tool metadata; stronger evidence should be attached for private reads and writes."
      })
    ],
    riskDomain: inferRiskDomain(input.toolName, metadata),
    proposedArguments: input.proposedArguments ?? {},
    recommendedRoute: (metadata.recommended_route as ToolPrecheckAction | undefined) ?? input.recommendedRoute ?? "accept",
    requestId: input.requestId ?? (metadata.request_id as string | undefined),
    agentId: input.agentId ?? (metadata.agent_id as string | undefined),
    userIntent: input.userIntent ?? (metadata.user_intent as string | undefined),
    authorizationSubject: metadata.authorization_subject as AuthorizationSubject | undefined
  });
}

export function gateToolCall(input: {
  toolName: string;
  proposedArguments?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  evidenceRefs?: ToolEvidenceRef[];
  raiseOnBlock?: boolean;
  executionMode?: "enforce" | "shadow";
  onDecision?: (gate: AanaGateResult) => void;
}): AanaGateResult {
  const event = buildPrecheckFromToolCall(input);
  const result = checkToolCall(event);
  const policy = executionPolicy(result, input.executionMode ?? "enforce");
  const allowed = policy.aana_allows_execution;
  const gate: AanaGateResult = { event, result, allowed, execution_allowed: policy.execution_allowed, execution_policy: policy };
  if (!gate.execution_allowed) gate.error = middlewareError(result, event, policy);
  input.onDecision?.(gate);
  if ((input.raiseOnBlock ?? true) && !gate.execution_allowed) throw new AanaToolExecutionBlocked(result, event, gate.error);
  return gate;
}

export function guardToolFunction<TArgs extends unknown[], TResult>(
  toolName: string,
  fn: (...args: TArgs) => TResult,
  metadata: Record<string, unknown> = {},
  options: { raiseOnBlock?: boolean; executionMode?: "enforce" | "shadow"; onDecision?: (gate: AanaGateResult) => void } = {}
): (...args: TArgs) => TResult {
  return (...args: TArgs) => {
    const proposedArguments = args.length === 1 && typeof args[0] === "object" && args[0] !== null ? (args[0] as Record<string, unknown>) : { args };
    const gate = gateToolCall({ toolName, proposedArguments, metadata, raiseOnBlock: options.raiseOnBlock, executionMode: options.executionMode, onDecision: options.onDecision });
    if (!gate.execution_allowed) return gate as TResult;
    return fn(...args);
  };
}

export const wrapAgentTool = guardToolFunction;
export const langChainToolMiddleware = guardToolFunction;
export const openAIAgentsToolMiddleware = guardToolFunction;
export const autoGenToolMiddleware = guardToolFunction;
export const crewAIToolMiddleware = guardToolFunction;
export const mcpToolMiddleware = guardToolFunction;

export interface FamilyAanaClientOptions extends AanaClientOptions {
  familyId?: string;
  adapterAliases?: Record<string, string>;
}

export class AanaClient {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly timeoutMs: number;
  private readonly shadowMode: boolean;
  private readonly fetchImpl: typeof fetch;

  constructor(options: AanaClientOptions) {
    if (!options.baseUrl) throw new Error("baseUrl is required.");
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.token = options.token;
    this.timeoutMs = options.timeoutMs ?? 10000;
    this.shadowMode = options.shadowMode ?? false;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  evidence(evidence?: EvidenceInput | EvidenceInput[], defaults: Partial<EvidenceObject> = {}): EvidenceInput[] {
    return normalizeEvidence(evidence, defaults);
  }

  workflowRequest(input: Parameters<typeof workflowRequest>[0]): WorkflowRequest {
    return workflowRequest(input);
  }

  agentEvent(input: Parameters<typeof agentEvent>[0]): AgentEvent {
    return agentEvent(input);
  }

  toolPrecheckEvent(input: Parameters<typeof toolPrecheckEvent>[0]): ToolPrecheckEvent {
    return toolPrecheckEvent(input);
  }

  ready(): Promise<AanaClientResult> {
    return this.request("GET", "/ready");
  }

  validateEvent(event: AgentEvent): Promise<AanaClientResult> {
    return this.request("POST", "/validate-event", event);
  }

  agentCheck(event: AgentEvent, options: { adapterId?: string; shadowMode?: boolean } = {}): Promise<AanaClientResult> {
    const query: Record<string, string> = {};
    if (options.adapterId) query.adapter_id = options.adapterId;
    if (options.shadowMode ?? this.shadowMode) query.shadow_mode = "true";
    return this.request("POST", "/agent-check", event, query);
  }

  validateWorkflow(request: WorkflowRequest): Promise<AanaClientResult> {
    return this.request("POST", "/validate-workflow", request);
  }

  validateToolPrecheck(event: ToolPrecheckEvent): Promise<AanaClientResult> {
    return this.request("POST", "/validate-tool-precheck", event);
  }

  workflowCheck(request: WorkflowRequest, options: { shadowMode?: boolean } = {}): Promise<AanaClientResult> {
    const query: Record<string, string> = {};
    if (options.shadowMode ?? this.shadowMode) query.shadow_mode = "true";
    return this.request("POST", "/workflow-check", request, query);
  }

  workflowBatch(requests: WorkflowRequest[], batchId?: string, options: { shadowMode?: boolean } = {}): Promise<AanaClientResult> {
    const query: Record<string, string> = {};
    if (options.shadowMode ?? this.shadowMode) query.shadow_mode = "true";
    return this.request("POST", "/workflow-batch", { contract_version: "0.1", batch_id: batchId, requests }, query);
  }

  toolPrecheck(event: ToolPrecheckEvent, options: { shadowMode?: boolean } = {}): Promise<AanaClientResult> {
    const query: Record<string, string> = {};
    if (options.shadowMode ?? this.shadowMode) query.shadow_mode = "true";
    return this.request("POST", "/tool-precheck", event, query);
  }

  private async request(method: "GET" | "POST", path: string, body?: unknown, query: Record<string, string> = {}): Promise<AanaClientResult> {
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(query)) {
      url.searchParams.set(key, value);
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetchImpl(url, {
        method,
        headers: {
          ...(body === undefined ? {} : { "content-type": "application/json" }),
          ...(this.token ? { authorization: `Bearer ${this.token}` } : {})
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal
      });
      const text = await response.text();
      const payload = text ? JSON.parse(text) : {};
      if (!response.ok) {
        throw new Error(`AANA bridge HTTP ${response.status}: ${JSON.stringify(payload)}`);
      }
      return payload;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export class FamilyAanaClient extends AanaClient {
  readonly familyId: string;
  readonly adapterAliases: Record<string, string>;

  constructor(options: FamilyAanaClientOptions) {
    super(options);
    this.familyId = options.familyId ?? "custom";
    this.adapterAliases = options.adapterAliases ?? {};
  }

  resolveAdapter(adapter: string): string {
    return this.adapterAliases[adapter] ?? adapter;
  }

  workflowRequest(input: Parameters<typeof workflowRequest>[0]): WorkflowRequest {
    return familyWorkflowRequest(this.familyId, {
      ...input,
      adapter: this.resolveAdapter(input.adapter)
    });
  }

  agentEvent(input: Parameters<typeof agentEvent>[0]): AgentEvent {
    return agentEvent({
      ...input,
      adapterId: input.adapterId ? this.resolveAdapter(input.adapterId) : undefined,
      metadata: { ...(input.metadata ?? {}), aana_family: this.familyId }
    });
  }

  evidenceObject(text: string, defaults: EvidenceObject & { source_id: string }): EvidenceObject {
    return evidenceObject(text, defaults);
  }
}

export class EnterpriseAANAClient extends FamilyAanaClient {
  constructor(options: AanaClientOptions) {
    super({ ...options, familyId: "enterprise", adapterAliases: FAMILY_ADAPTER_ALIASES.enterprise });
  }
}

export class SupportAANAClient extends FamilyAanaClient {
  constructor(options: AanaClientOptions) {
    super({ ...options, familyId: "support", adapterAliases: FAMILY_ADAPTER_ALIASES.support });
  }
}

export class PersonalAANAClient extends FamilyAanaClient {
  constructor(options: AanaClientOptions) {
    super({
      ...options,
      familyId: "personal_productivity",
      adapterAliases: FAMILY_ADAPTER_ALIASES.personal_productivity
    });
  }
}

export class CivicAANAClient extends FamilyAanaClient {
  constructor(options: AanaClientOptions) {
    super({ ...options, familyId: "government_civic", adapterAliases: FAMILY_ADAPTER_ALIASES.government_civic });
  }
}

export function createAanaClient(options: AanaClientOptions): AanaClient {
  return new AanaClient(options);
}
