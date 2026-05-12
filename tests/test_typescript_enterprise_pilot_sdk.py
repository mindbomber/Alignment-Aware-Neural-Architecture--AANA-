import json
import pathlib
import shutil
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TS_SDK = ROOT / "sdk" / "typescript"


class TypeScriptEnterprisePilotSdkTests(unittest.TestCase):
    def test_typescript_sdk_exports_enterprise_pilot_client_methods_and_types(self):
        source = (TS_SDK / "src" / "index.ts").read_text(encoding="utf-8")

        self.assertIn("export interface AIxAuditRequest", source)
        self.assertIn("export interface AIxAuditResult", source)
        self.assertIn("export interface DurableAuditStorageResult", source)
        self.assertIn("export interface HumanReviewExportResult", source)
        self.assertIn("export interface LiveMonitoringResult", source)
        self.assertIn("export interface EnterpriseConnectorReadinessResult", source)
        self.assertIn("export interface EnterpriseLiveConnectorsResult", source)
        self.assertIn("export interface ProductionCandidateProfileResult", source)
        self.assertIn("export interface ProductionCandidateCheckResult", source)
        self.assertIn("export interface EnterpriseSupportDemoResult", source)
        self.assertIn("aixAudit(request: AIxAuditRequest", source)
        self.assertIn("durableAuditStorage(request: DurableAuditStorageRequest", source)
        self.assertIn("humanReviewExport(request: HumanReviewExportRequest", source)
        self.assertIn("liveMonitoring(request: LiveMonitoringRequest", source)
        self.assertIn("enterpriseConnectors(): Promise<EnterpriseConnectorReadinessResult>", source)
        self.assertIn("enterpriseLiveConnectors(request: EnterpriseLiveConnectorsRequest", source)
        self.assertIn("productionCandidateProfile(request: ProductionCandidateProfileRequest", source)
        self.assertIn("productionCandidateCheck(request: ProductionCandidateCheckRequest", source)
        self.assertIn("enterpriseSupportDemo(request: EnterpriseSupportDemoRequest", source)

    def test_typescript_sdk_enterprise_pilot_http_parity(self):
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        node = shutil.which("node.exe") or shutil.which("node")
        if npm is None or node is None:
            self.skipTest("npm/node is not available")

        subprocess.run([npm, "run", "build"], cwd=TS_SDK, check=True, capture_output=True, text=True)
        script = textwrap.dedent(
            """
            import {
              EnterpriseOpsPilotAANAClient,
              FAMILY_ADAPTER_ALIASES,
              routeAllowsExecution
            } from './dist/index.js';

            const calls = [];
            const responses = {
              '/aix-audit': {
                aix_audit_report_version: '0.1',
                valid: true,
                product: 'AANA AIx Audit',
                product_bundle: 'enterprise_ops_pilot',
                deployment_recommendation: 'pilot_ready_with_controls',
                summary: {
                  workflow_count: 8,
                  audit_records: 8,
                  output_dir: 'out/aix',
                  audit_log: 'out/aix/audit.jsonl',
                  metrics: 'out/aix/metrics.json',
                  drift_report: 'out/aix/aix-drift.json',
                  integrity_manifest: 'out/aix/audit-integrity.json',
                  reviewer_report: 'out/aix/reviewer-report.md',
                  enterprise_dashboard: 'out/aix/enterprise-dashboard.json',
                  enterprise_connector_readiness: 'out/aix/enterprise-connector-readiness.json',
                  aix_report_json: 'out/aix/aix-report.json',
                  aix_report_md: 'out/aix/aix-report.md',
                  materialized_batch: 'out/aix/enterprise-workflow-batch.json'
                },
                aix_report: {
                  limitations: ['Pilot readiness is not production certification.']
                },
                enterprise_dashboard: {
                  cards: { pass: 8, shadow_would_intervene: 8, hard_blockers: 0 },
                  recommended_actions: { revise: 8 }
                }
              },
              '/enterprise-connectors': {
                plan: {
                  enterprise_connector_readiness_version: '0.1',
                  plan_type: 'aana_enterprise_ops_connector_readiness',
                  product_bundle: 'enterprise_ops_pilot',
                  summary: {
                    connector_count: 7,
                    required_connector_ids: ['crm_support', 'ticketing', 'email_send', 'iam', 'ci', 'deployment', 'data_export'],
                    live_execution_enabled_count: 0,
                    write_capable_connector_count: 4,
                    shadow_mode_default: true
                  },
                  connectors: [
                    {
                      connector_id: 'email_send',
                      live_execution_enabled: false,
                      default_runtime_route_before_approval: 'defer',
                      auth_requirements: { tokens_in_audit_logs: false },
                      redaction_requirements: { raw_private_content_allowed_in_audit: false },
                      shadow_mode_requirements: { write_operations_disabled: true }
                    }
                  ]
                },
                validation: { valid: true, errors: 0, warnings: 0, connector_count: 7, issues: [] }
              },
              '/durable-audit-storage': {
                durable_audit_storage_version: '0.1',
                storage_type: 'aana_durable_audit_storage',
                storage_mode: 'local_append_only',
                audit_path: 'out/durable/aana_audit.jsonl',
                manifest_path: 'out/durable/aana_audit.jsonl.sha256.json',
                record_count: 8,
                line_count: 8,
                append_only: true,
                redacted_records_only: true,
                raw_payload_storage: 'disabled',
                manifest_sha256: 'abc'
              },
              '/human-review-export': {
                runtime_human_review_version: '0.1',
                export_type: 'aana_runtime_human_review_export',
                valid: true,
                audit_log_path: 'out/aix/audit.jsonl',
                queue_path: 'out/review/queue.jsonl',
                summary_path: 'out/review/summary.json',
                packet_count: 2,
                include_all: false,
                append: false,
                summary: {
                  packet_count: 2,
                  redacted_records_only: true,
                  raw_payload_logged: false,
                  review_status: { open: 2 },
                  by_queue: { support_human_review: 2 },
                  by_priority: { critical: 1, high: 1 },
                  by_recommended_action: { defer: 1, revise: 1 },
                  by_adapter: { support_reply: 2 },
                  hard_blockers: { missing_policy_evidence: 1 },
                  violation_codes: { recommended_action_not_allowed: 1 }
                }
              },
              '/live-monitoring': {
                live_monitoring_version: '0.1',
                report_type: 'aana_live_monitoring_report',
                status: 'healthy',
                healthy: true,
                audit_log_path: 'out/aix/audit.jsonl',
                record_count: 8,
                redacted_records_only: true,
                raw_payload_logged: false,
                thresholds: { min_records: 1, min_aix_average: 0.85 },
                checks: [{ metric: 'aix_score_average', status: 'healthy', value: 0.92, threshold: 0.85 }],
                summary: { critical_count: 0, warning_count: 0, aix_average: 0.92 },
                cards: { total_records: 8, hard_blocker_total: 0 },
                metrics: { audit_records_total: 8, aix_score_average: 0.92 },
                dashboard: { shadow_mode: { would_block_rate: 0.0 } },
                claim_boundary: 'Live monitoring readiness only; not production certification or go-live approval.'
              },
              '/enterprise-live-connectors': {
                enterprise_live_connectors_version: '0.1',
                config_type: 'aana_enterprise_support_live_connectors',
                valid: true,
                mode: 'dry_run',
                claim_boundary: 'Connector smoke evidence only; not production certification.',
                validation: {
                  valid: true,
                  issues: [],
                  summary: {
                    connector_count: 3,
                    required_connector_ids: ['crm_support', 'email_send', 'ticketing'],
                    live_approved_count: 0,
                    write_enabled_count: 0
                  }
                },
                results: {
                  crm_support: { connector_id: 'crm_support', operation: 'fetch_support_case_context', executed: false, route: 'dry_run', raw_payload_logged: false },
                  email_send: { connector_id: 'email_send', operation: 'send_email', executed: false, route: 'dry_run', raw_payload_logged: false },
                  ticketing: { connector_id: 'ticketing', operation: 'update_ticket', executed: false, route: 'defer', raw_payload_logged: false }
                },
                summary: {
                  connector_count: 3,
                  executed_count: 0,
                  blocked_count: 1,
                  raw_payload_logged: false
                }
              },
              '/enterprise-support-demo': {
                enterprise_support_demo_version: '0.1',
                valid: true,
                product: 'AANA AIx Audit',
                product_bundle: 'enterprise_ops_pilot',
                wedge: 'customer support + email send + ticket update',
                claim_boundary: 'Pilot demo evidence only; not production certification.',
                steps: [
                  { stage: 'support_reply', aana_check: { recommended_action: 'revise' }, aix: { score: 1.0, hard_blockers: [] } },
                  { stage: 'email_send', aana_check: { recommended_action: 'defer' }, aix: { score: 0.93, hard_blockers: ['recommended_action_not_allowed'] } },
                  { stage: 'ticket_update', aana_check: { recommended_action: 'revise' }, aix: { score: 1.0, hard_blockers: [] } }
                ],
                dashboard_cards: { shadow_would_intervene: 3, shadow_would_block: 1, hard_blockers: 1 },
                dashboard_metrics: { recommended_actions: { revise: 2, defer: 1 } },
                aix_report_summary: { deployment_recommendation: 'not_pilot_ready' },
                artifacts: { demo_flow: 'out/demo/demo-flow.json', aix_report_md: 'out/demo/aix-report.md' }
              },
              '/production-candidate-profile': {
                profile: {
                  production_candidate_profile_version: '0.1',
                  profile_type: 'aana_production_candidate_profile',
                  profile_id: 'enterprise_support_email_ticket_candidate',
                  product_bundle: 'enterprise_ops_pilot',
                  status: 'production_candidate_config',
                  claim_boundary: 'Production-candidate configuration only; not production certification or go-live approval.'
                },
                validation: {
                  valid: true,
                  production_candidate_ready: true,
                  go_live_ready: false,
                  errors: 0,
                  warnings: 2,
                  issues: [],
                  component_reports: { live_connector_config: { summary: { write_enabled_count: 0 } } },
                  summary: { wedge: 'customer support + email send + ticket update' }
                }
              },
              '/production-candidate-check': {
                production_candidate_check_version: '0.1',
                check_type: 'aana_production_candidate_check',
                valid: true,
                production_candidate_ready: true,
                go_live_ready: false,
                status: 'warn',
                errors: 0,
                warnings: 2,
                issues: [],
                profile_path: 'examples/production_candidate_profile_enterprise_support.json',
                artifact_dir: 'out/aix',
                artifact_summary: { audit_records: 8, monitoring_status: 'critical' },
                component_reports: { profile: { valid: true } },
                claim_boundary: 'Production-candidate readiness only; not production certification or go-live approval.'
              }
            };

            const fetchImpl = async (url, init = {}) => {
              const parsed = new URL(url);
              calls.push({
                path: parsed.pathname,
                method: init.method,
                auth: init.headers?.authorization,
                body: init.body ? JSON.parse(init.body) : undefined
              });
              const payload = responses[parsed.pathname];
              if (!payload) {
                return { ok: false, status: 404, text: async () => JSON.stringify({ error: 'not_found' }) };
              }
              return { ok: true, status: 200, text: async () => JSON.stringify(payload) };
            };

            const client = new EnterpriseOpsPilotAANAClient({
              baseUrl: 'http://127.0.0.1:8766',
              token: 'secret-token',
              shadowMode: true,
              fetchImpl
            });

            if (client.resolveAdapter('email') !== 'email_send_guardrail') throw new Error('enterprise_ops_pilot email alias mismatch');
            if (FAMILY_ADAPTER_ALIASES.enterprise_ops_pilot.ticket !== 'ticket_update_checker') throw new Error('ticket alias mismatch');
            if (routeAllowsExecution('defer') !== false) throw new Error('defer must not allow execution');

            const audit = await client.aixAudit({ output_dir: 'out/aix' });
            const durable = await client.durableAuditStorage({ source_audit_log: 'out/aix/audit.jsonl' });
            const review = await client.humanReviewExport({ audit_log_path: 'out/aix/audit.jsonl', queue_path: 'out/review/queue.jsonl', summary_path: 'out/review/summary.json' });
            const monitoring = await client.liveMonitoring({ audit_log_path: 'out/aix/audit.jsonl', output_path: 'out/monitoring/live.json' });
            const connectors = await client.enterpriseConnectors();
            const liveConnectors = await client.enterpriseLiveConnectors({ mode: 'dry_run', output_path: 'out/connectors.json' });
            const profile = await client.productionCandidateProfile({ profile_path: 'examples/production_candidate_profile_enterprise_support.json' });
            const candidateCheck = await client.productionCandidateCheck({ profile_path: 'examples/production_candidate_profile_enterprise_support.json', artifact_dir: 'out/aix' });
            const demo = await client.enterpriseSupportDemo({ output_dir: 'out/demo' });

            if (audit.product_bundle !== 'enterprise_ops_pilot') throw new Error('audit product bundle mismatch');
            if (audit.summary.workflow_count !== 8 || audit.summary.audit_records !== 8) throw new Error('audit summary mismatch');
            if (audit.deployment_recommendation !== 'pilot_ready_with_controls') throw new Error('audit recommendation mismatch');
            if (!String(audit.aix_report.limitations[0]).toLowerCase().includes('not production certification')) throw new Error('missing pilot boundary');

            if (durable.storage_type !== 'aana_durable_audit_storage') throw new Error('durable storage type mismatch');
            if (durable.raw_payload_storage !== 'disabled') throw new Error('durable storage must disable raw payloads');
            if (durable.append_only !== true) throw new Error('durable storage must be append-only');

            if (review.export_type !== 'aana_runtime_human_review_export') throw new Error('human-review export type mismatch');
            if (review.packet_count !== 2) throw new Error('human-review packet count mismatch');
            if (review.summary.raw_payload_logged !== false) throw new Error('human-review export must not log raw payloads');

            if (monitoring.status !== 'healthy') throw new Error('live monitoring should be healthy');
            if (monitoring.raw_payload_logged !== false) throw new Error('live monitoring must not log raw payloads');
            if (!monitoring.claim_boundary.toLowerCase().includes('not production certification')) throw new Error('monitoring boundary missing');

            if (!connectors.validation.valid) throw new Error('connector validation should pass');
            if (connectors.plan.summary.connector_count !== 7) throw new Error('connector count mismatch');
            if (connectors.plan.summary.live_execution_enabled_count !== 0) throw new Error('connectors must not enable live execution');
            if (connectors.plan.connectors[0].default_runtime_route_before_approval !== 'defer') throw new Error('connector preapproval route mismatch');

            if (!liveConnectors.valid) throw new Error('live connector smoke should pass');
            if (liveConnectors.summary.connector_count !== 3) throw new Error('live connector count mismatch');
            if (liveConnectors.summary.executed_count !== 0) throw new Error('dry-run live connector smoke must not execute');
            if (liveConnectors.summary.raw_payload_logged !== false) throw new Error('live connector smoke must not log raw payloads');

            if (!profile.validation.production_candidate_ready) throw new Error('production candidate profile should be ready');
            if (profile.validation.go_live_ready !== false) throw new Error('default profile should not be go-live ready');
            if (!profile.profile.claim_boundary.toLowerCase().includes('not production certification')) throw new Error('profile boundary missing');

            if (!candidateCheck.production_candidate_ready) throw new Error('production candidate check should be ready');
            if (candidateCheck.go_live_ready !== false) throw new Error('production candidate check should not be go-live ready');
            if (!candidateCheck.claim_boundary.toLowerCase().includes('not production certification')) throw new Error('candidate check boundary missing');

            if (demo.wedge !== 'customer support + email send + ticket update') throw new Error('demo wedge mismatch');
            if (demo.steps.length !== 3) throw new Error('demo step count mismatch');
            if (demo.steps.find((step) => step.stage === 'email_send').aana_check.recommended_action !== 'defer') throw new Error('email step must defer');
            if (!demo.steps.find((step) => step.stage === 'email_send').aix.hard_blockers.includes('recommended_action_not_allowed')) throw new Error('email hard blocker missing');
            if (demo.dashboard_cards.shadow_would_block !== 1) throw new Error('shadow would-block mismatch');
            if (demo.aix_report_summary.deployment_recommendation !== 'not_pilot_ready') throw new Error('demo recommendation mismatch');

            if (calls.map((call) => call.path).join(',') !== '/aix-audit,/durable-audit-storage,/human-review-export,/live-monitoring,/enterprise-connectors,/enterprise-live-connectors,/production-candidate-profile,/production-candidate-check,/enterprise-support-demo') {
              throw new Error(`unexpected route sequence: ${JSON.stringify(calls)}`);
            }
            if (calls.some((call) => call.auth !== 'Bearer secret-token')) throw new Error('authorization header missing');
            if (calls[0].body.shadow_mode !== true) throw new Error('aixAudit should inherit client shadowMode');
            if (calls[1].body.source_audit_log !== 'out/aix/audit.jsonl') throw new Error('durableAuditStorage should send source audit log');
            if (calls[2].body.queue_path !== 'out/review/queue.jsonl') throw new Error('humanReviewExport should send queue path');
            if (calls[3].body.output_path !== 'out/monitoring/live.json') throw new Error('liveMonitoring should send output path');
            if (calls[5].body.mode !== 'dry_run') throw new Error('enterpriseLiveConnectors should send requested mode');
            if (calls[6].body.profile_path !== 'examples/production_candidate_profile_enterprise_support.json') throw new Error('productionCandidateProfile should send profile path');
            if (calls[7].body.artifact_dir !== 'out/aix') throw new Error('productionCandidateCheck should send artifact dir');
            if (calls[8].body.shadow_mode !== true) throw new Error('enterpriseSupportDemo should inherit client shadowMode');

            console.log(JSON.stringify({ ok: true, calls }));
            """
        )

        completed = subprocess.run(
            [node, "--input-type=module", "-e", script],
            cwd=TS_SDK,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}")
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            [call["path"] for call in payload["calls"]],
            [
                "/aix-audit",
                "/durable-audit-storage",
                "/human-review-export",
                "/live-monitoring",
                "/enterprise-connectors",
                "/enterprise-live-connectors",
                "/production-candidate-profile",
                "/production-candidate-check",
                "/enterprise-support-demo",
            ],
        )


if __name__ == "__main__":
    unittest.main()
