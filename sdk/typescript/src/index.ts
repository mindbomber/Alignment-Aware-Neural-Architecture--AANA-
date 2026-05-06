export type AanaAction = "accept" | "revise" | "retrieve" | "ask" | "defer" | "refuse";

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

  workflowCheck(request: WorkflowRequest, options: { shadowMode?: boolean } = {}): Promise<AanaClientResult> {
    const query = options.shadowMode ?? this.shadowMode ? { shadow_mode: "true" } : {};
    return this.request("POST", "/workflow-check", request, query);
  }

  workflowBatch(requests: WorkflowRequest[], batchId?: string, options: { shadowMode?: boolean } = {}): Promise<AanaClientResult> {
    const query = options.shadowMode ?? this.shadowMode ? { shadow_mode: "true" } : {};
    return this.request("POST", "/workflow-batch", { contract_version: "0.1", batch_id: batchId, requests }, query);
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
