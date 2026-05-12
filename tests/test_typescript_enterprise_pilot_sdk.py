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
        self.assertIn("export interface EnterpriseConnectorReadinessResult", source)
        self.assertIn("export interface EnterpriseSupportDemoResult", source)
        self.assertIn("aixAudit(request: AIxAuditRequest", source)
        self.assertIn("enterpriseConnectors(): Promise<EnterpriseConnectorReadinessResult>", source)
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
            const connectors = await client.enterpriseConnectors();
            const demo = await client.enterpriseSupportDemo({ output_dir: 'out/demo' });

            if (audit.product_bundle !== 'enterprise_ops_pilot') throw new Error('audit product bundle mismatch');
            if (audit.summary.workflow_count !== 8 || audit.summary.audit_records !== 8) throw new Error('audit summary mismatch');
            if (audit.deployment_recommendation !== 'pilot_ready_with_controls') throw new Error('audit recommendation mismatch');
            if (!String(audit.aix_report.limitations[0]).toLowerCase().includes('not production certification')) throw new Error('missing pilot boundary');

            if (!connectors.validation.valid) throw new Error('connector validation should pass');
            if (connectors.plan.summary.connector_count !== 7) throw new Error('connector count mismatch');
            if (connectors.plan.summary.live_execution_enabled_count !== 0) throw new Error('connectors must not enable live execution');
            if (connectors.plan.connectors[0].default_runtime_route_before_approval !== 'defer') throw new Error('connector preapproval route mismatch');

            if (demo.wedge !== 'customer support + email send + ticket update') throw new Error('demo wedge mismatch');
            if (demo.steps.length !== 3) throw new Error('demo step count mismatch');
            if (demo.steps.find((step) => step.stage === 'email_send').aana_check.recommended_action !== 'defer') throw new Error('email step must defer');
            if (!demo.steps.find((step) => step.stage === 'email_send').aix.hard_blockers.includes('recommended_action_not_allowed')) throw new Error('email hard blocker missing');
            if (demo.dashboard_cards.shadow_would_block !== 1) throw new Error('shadow would-block mismatch');
            if (demo.aix_report_summary.deployment_recommendation !== 'not_pilot_ready') throw new Error('demo recommendation mismatch');

            if (calls.map((call) => call.path).join(',') !== '/aix-audit,/enterprise-connectors,/enterprise-support-demo') {
              throw new Error(`unexpected route sequence: ${JSON.stringify(calls)}`);
            }
            if (calls.some((call) => call.auth !== 'Bearer secret-token')) throw new Error('authorization header missing');
            if (calls[0].body.shadow_mode !== true) throw new Error('aixAudit should inherit client shadowMode');
            if (calls[2].body.shadow_mode !== true) throw new Error('enterpriseSupportDemo should inherit client shadowMode');

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
        self.assertEqual([call["path"] for call in payload["calls"]], ["/aix-audit", "/enterprise-connectors", "/enterprise-support-demo"])


if __name__ == "__main__":
    unittest.main()
