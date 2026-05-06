import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_release_bundle import DEFAULT_ARTIFACTS, create_mi_release_bundle


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MIReleaseBundleTests(unittest.TestCase):
    def test_release_bundle_copies_required_artifacts_and_hashes_them(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = create_mi_release_bundle(directory)
            manifest = payload["manifest"]
            manifest_path = Path(payload["paths"]["release_manifest"])

            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["artifacts"]), set(DEFAULT_ARTIFACTS))
            for item in manifest["artifacts"].values():
                bundle_path = Path(item["bundle_path"])
                self.assertTrue(bundle_path.exists())
                self.assertEqual(item["sha256"], sha256(bundle_path))
                self.assertGreater(item["bytes"], 0)

        self.assertEqual(loaded, manifest)

    def test_release_bundle_manifest_records_release_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = create_mi_release_bundle(directory)["manifest"]

        self.assertEqual(manifest["mi_release_bundle_version"], "0.1")
        self.assertEqual(manifest["rc_status"], "pass")
        self.assertEqual(manifest["readiness_status"], "ready")
        self.assertEqual(manifest["global_aix"]["score"], 1.0)
        self.assertEqual(manifest["unresolved_blocker_count"], 0)

    def test_release_bundle_writes_short_release_note(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = create_mi_release_bundle(directory)
            note = Path(payload["paths"]["release_note"]).read_text(encoding="utf-8")

        self.assertIn("AANA MI Release Candidate Evidence Bundle", note)
        self.assertIn("Status: pass", note)
        self.assertIn("Out of scope", note)
        self.assertIn("External production deployment approval", note)

    def test_release_bundle_cli_outputs_bundle_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/mi_release_bundle.py",
                    "--output-dir",
                    directory,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass -- readiness=ready", completed.stdout)
        self.assertIn("global_aix=1.0", completed.stdout)


if __name__ == "__main__":
    unittest.main()
