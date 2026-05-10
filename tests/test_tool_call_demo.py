import pathlib
import json
import shutil
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "tool-call-demo"


class ToolCallDemoTests(unittest.TestCase):
    def test_static_demo_files_exist_and_link_assets(self):
        html = (DEMO / "index.html").read_text(encoding="utf-8")

        self.assertIn("Try AANA", html)
        self.assertIn("An agent proposes a tool call", html)
        self.assertIn("A plain permissive agent would execute", html)
        self.assertIn("Pick an example, click Run Gate", html)
        self.assertIn("Allowed: confirmed write", html)
        self.assertIn("Blocked: write missing confirmation", html)
        self.assertIn("Blocked: private read missing auth", html)
        self.assertIn("Blocked: unknown destructive tool", html)
        self.assertIn('href="app.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertTrue((DEMO / "app.css").exists())
        self.assertTrue((DEMO / "app.js").exists())

    def test_demo_has_contract_fields_and_decision_surface(self):
        html = (DEMO / "index.html").read_text(encoding="utf-8")

        for item in [
            "tool-json",
            "tool-category",
            "authorization-state",
            "risk-domain",
            "runtime-route",
            "evidence-json",
            "gate-decision",
            "recommended-action",
            "aix-score",
            "execution-status",
            "execution-proof",
        ]:
            self.assertIn(item, html)

    def test_browser_gate_logic_contains_aana_routes_and_blockers(self):
        script = (DEMO / "app.js").read_text(encoding="utf-8")

        self.assertIn("aana.agent_tool_precheck.v1", script)
        self.assertIn("private_read_has_authenticated_context", script)
        self.assertIn("write_missing_validation_or_confirmation", script)
        self.assertIn("evidence_missing_authorization", script)
        self.assertIn("schema_validation_failed", script)
        self.assertIn("public_read_allowed_without_identity_auth", script)
        self.assertIn("unknown_destructive_tool_refused", script)
        self.assertIn("guardedSyntheticExecution", script)
        self.assertIn("synthetic_executor_call_count_after", script)

    def test_demo_examples_route_and_execute_as_documented(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const source = fs.readFileSync("docs/tool-call-demo/app.js", "utf8") +
              "\nglobalThis.__aanaDemo = { examples, el, loadExample, runGate, gateEvent, normalizeEvent };";

            function fakeEl() {
              return {
                value: "",
                textContent: "",
                innerHTML: "",
                dataset: {},
                addEventListener() {},
                append(child) {
                  this.children = (this.children || []).concat([child]);
                }
              };
            }

            const byId = {};
            const ids = [
              "tool-json",
              "evidence-json",
              "tool-category",
              "authorization-state",
              "risk-domain",
              "runtime-route",
              "gate-decision",
              "recommended-action",
              "aix-score",
              "execution-status",
              "gate-card",
              "action-card",
              "execution-card",
              "blockers",
              "reasons",
              "execution-proof",
              "event-output",
              "result-output",
              "run-gate",
              "load-accept",
              "load-ask",
              "load-defer",
              "load-refuse"
            ];
            for (const id of ids) byId[id] = fakeEl();
            global.document = {
              querySelector(selector) {
                return byId[selector.slice(1)] || fakeEl();
              },
              createElement() {
                return fakeEl();
              }
            };

            eval(source);

            const demo = globalThis.__aanaDemo;
            const observed = {};
            for (const kind of ["accept", "ask", "defer", "refuse"]) {
              demo.loadExample(kind);
              const result = JSON.parse(demo.el.resultOutput.textContent);
              const proof = JSON.parse(demo.el.executionProof.textContent);
              observed[kind] = {
                route: result.recommended_action,
                executorCalls: proof.synthetic_executor_call_count_after,
                blockedProof: proof.blocked_tool_non_execution_proven,
                blockers: result.hard_blockers || [],
                reasons: result.reasons || []
              };
            }
            console.log(JSON.stringify(observed));
            """
        )

        completed = subprocess.run(
            [node, "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        observed = json.loads(completed.stdout)

        self.assertEqual(observed["accept"]["route"], "accept")
        self.assertEqual(observed["accept"]["executorCalls"], 1)
        self.assertFalse(observed["accept"]["blockedProof"])

        self.assertEqual(observed["ask"]["route"], "ask")
        self.assertEqual(observed["ask"]["executorCalls"], 0)
        self.assertTrue(observed["ask"]["blockedProof"])

        self.assertEqual(observed["defer"]["route"], "defer")
        self.assertEqual(observed["defer"]["executorCalls"], 0)
        self.assertTrue(observed["defer"]["blockedProof"])

        self.assertEqual(observed["refuse"]["route"], "refuse")
        self.assertEqual(observed["refuse"]["executorCalls"], 0)
        self.assertTrue(observed["refuse"]["blockedProof"])
        self.assertIn("unknown_destructive_tool", observed["refuse"]["blockers"])

    def test_docs_link_to_tool_call_demo(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        index = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        try_demo = (ROOT / "docs" / "try-demo" / "index.md").read_text(encoding="utf-8")

        self.assertIn("docs/tool-call-demo/index.html", readme)
        self.assertIn("tool-call-demo/", index)
        self.assertIn("../tool-call-demo/index.html", try_demo)


if __name__ == "__main__":
    unittest.main()
