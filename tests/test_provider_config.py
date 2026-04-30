import os
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from common import responses_api_config


class ProviderConfigTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            key: os.environ.get(key)
            for key in [
                "AANA_API_KEY",
                "OPENAI_API_KEY",
                "AANA_BASE_URL",
                "OPENAI_BASE_URL",
                "AANA_RESPONSES_URL",
                "OPENAI_RESPONSES_URL",
            ]
        }
        for key in self.original:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self.original.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value

    def test_defaults_to_openai_responses_url(self):
        os.environ["OPENAI_API_KEY"] = "test-key"

        url, api_key = responses_api_config()

        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(api_key, "test-key")

    def test_aana_key_and_base_url_override_default(self):
        os.environ["AANA_API_KEY"] = "adapter-key"
        os.environ["AANA_BASE_URL"] = "https://example.test/v1/"

        url, api_key = responses_api_config()

        self.assertEqual(url, "https://example.test/v1/responses")
        self.assertEqual(api_key, "adapter-key")

    def test_explicit_responses_url_wins_over_base_url(self):
        os.environ["AANA_API_KEY"] = "adapter-key"
        os.environ["AANA_BASE_URL"] = "https://example.test/v1"
        os.environ["AANA_RESPONSES_URL"] = "https://proxy.test/custom-responses"

        url, api_key = responses_api_config()

        self.assertEqual(url, "https://proxy.test/custom-responses")
        self.assertEqual(api_key, "adapter-key")


if __name__ == "__main__":
    unittest.main()
