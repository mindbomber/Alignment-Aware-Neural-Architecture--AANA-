import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ConservativeProductionPositioningTests(unittest.TestCase):
    def test_primary_public_surfaces_state_production_boundary(self):
        expected = "not production-certified by local tests alone"
        allowed_statuses = "demo-ready, pilot-ready, or production-candidate"
        required_gates = "live evidence connectors, domain owner signoff, audit retention, observability, human review path, security review, deployment manifest, incident response plan, and measured pilot results"
        paths = [
            ROOT / "README.md",
            ROOT / "docs" / "production-certification.md",
            ROOT / "docs" / "production-readiness-plan.md",
            ROOT / "docs" / "hosted-demo.md",
            ROOT / "docs" / "adapter-gallery.md",
            ROOT / "docs" / "demo" / "index.html",
            ROOT / "docs" / "adapter-gallery" / "index.html",
        ]

        for path in paths:
            text = path.read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIn(expected, normalized)
                self.assertIn(allowed_statuses, normalized)
                self.assertIn(required_gates, normalized)

    def test_readme_warns_local_checks_do_not_certify_production_safety(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Passing `pilot-certify`, `release-check`, or local tests does not certify production safety.", readme)


if __name__ == "__main__":
    unittest.main()
