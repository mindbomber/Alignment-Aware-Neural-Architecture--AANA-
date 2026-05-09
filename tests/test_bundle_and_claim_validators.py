import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BundleAndClaimValidatorTests(unittest.TestCase):
    def test_bundle_certification_validator_passes(self):
        completed = subprocess.run(
            [sys.executable, "scripts/validate_bundle_certification.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- bundles=3/3", completed.stdout)

    def test_public_claims_policy_validator_passes(self):
        completed = subprocess.run(
            [sys.executable, "scripts/validate_public_claims_policy.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- reports=", completed.stdout)


if __name__ == "__main__":
    unittest.main()
