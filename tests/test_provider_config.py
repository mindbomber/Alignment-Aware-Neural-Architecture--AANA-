import os
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from common import (
    anthropic_api_config,
    build_model_request,
    extract_response_text,
    model_provider,
    responses_api_config,
)


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
                "AANA_PROVIDER",
                "ANTHROPIC_API_KEY",
                "ANTHROPIC_BASE_URL",
                "ANTHROPIC_MESSAGES_URL",
                "ANTHROPIC_VERSION",
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

    def test_provider_aliases_default_to_openai(self):
        self.assertEqual(model_provider(), "openai")
        os.environ["AANA_PROVIDER"] = "claude"
        self.assertEqual(model_provider(), "anthropic")

    def test_openai_request_shape_is_responses_compatible(self):
        os.environ["OPENAI_API_KEY"] = "test-key"

        request = build_model_request(
            model="gpt-test",
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=123,
        )

        self.assertEqual(request["provider"], "openai")
        self.assertEqual(request["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(request["body"]["model"], "gpt-test")
        self.assertEqual(request["body"]["max_output_tokens"], 123)
        self.assertEqual(request["body"]["input"][0]["role"], "system")

    def test_anthropic_config_and_request_shape(self):
        os.environ["AANA_PROVIDER"] = "anthropic"
        os.environ["ANTHROPIC_API_KEY"] = "anthropic-key"
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.anthropic.test/v1/"
        os.environ["ANTHROPIC_VERSION"] = "2023-06-01"

        url, api_key, version = anthropic_api_config()
        request = build_model_request(
            model="claude-test",
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=321,
        )

        self.assertEqual(url, "https://api.anthropic.test/v1/messages")
        self.assertEqual(api_key, "anthropic-key")
        self.assertEqual(version, "2023-06-01")
        self.assertEqual(request["provider"], "anthropic")
        self.assertEqual(request["headers"]["x-api-key"], "anthropic-key")
        self.assertEqual(request["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(request["body"]["model"], "claude-test")
        self.assertEqual(request["body"]["system"], "system")
        self.assertEqual(request["body"]["max_tokens"], 321)
        self.assertEqual(request["body"]["messages"], [{"role": "user", "content": "user"}])

    def test_anthropic_response_text_extraction(self):
        payload = {
            "id": "msg_123",
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "name": "ignored"},
                {"type": "text", "text": "world"},
            ],
        }

        self.assertEqual(extract_response_text(payload), "hello\nworld")


if __name__ == "__main__":
    unittest.main()
