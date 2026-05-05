import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ConservativeProductionPositioningTests(unittest.TestCase):
    def test_primary_public_surfaces_state_production_boundary(self):
        expected = "not production-certified by itself"
        required_gates = "live evidence connectors, domain owner signoff, audit retention, observability, and human review paths"
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
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIn(expected, text)
                self.assertIn(required_gates, " ".join(text.split()))

    def test_readme_warns_local_checks_do_not_certify_production_safety(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Passing `pilot-certify`, `release-check`, or local tests does not certify production safety.", readme)


if __name__ == "__main__":
    unittest.main()
