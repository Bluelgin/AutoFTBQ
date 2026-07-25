import unittest
from unittest.mock import patch

from ai_clients import (
    DEEPSEEK_MODEL,
    GenericOpenAIClient,
    _response_content,
    create_chat_client,
)


class FakeChatResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{
                "message": {"content": "{}"},
                "finish_reason": "stop",
            }],
        }


class AIClientTests(unittest.TestCase):
    def test_custom_provider_uses_supplied_url_and_model(self):
        client = create_chat_client(
            "generic",
            api_key="secret",
            provider="第三方自定义",
            api_url="https://example.test/v1/chat/completions",
            api_model="custom-model",
        )

        self.assertIsInstance(client, GenericOpenAIClient)
        self.assertEqual(client.api_url, "https://example.test/v1/chat/completions")
        self.assertEqual(client.model, "custom-model")

    def test_legacy_custom_url_does_not_inherit_deepseek_options(self):
        client = create_chat_client(
            "generic",
            api_key="secret",
            api_url="https://example.test/v1/chat/completions",
            api_model="custom-model",
        )

        self.assertFalse(client.omit_temperature)
        self.assertEqual(client.request_overrides, {})

    def test_legacy_deepseek_client_uses_current_flash_model(self):
        client = create_chat_client("deepseek", api_key="secret")

        self.assertEqual(DEEPSEEK_MODEL, "deepseek-v4-flash")
        self.assertEqual(client.model, "deepseek-v4-flash")
        self.assertEqual(client.request_overrides, {"thinking": {"type": "disabled"}})

    @patch("ai_clients.requests.post", return_value=FakeChatResponse())
    def test_moonshot_migrates_old_default_and_omits_fixed_temperature(self, post):
        client = create_chat_client(
            "generic",
            api_key="secret",
            provider="Moonshot",
            api_model="moonshot-v1-8k",
        )

        client.chat([{"role": "user", "content": "test"}], temperature=0.45)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "kimi-k2.6")
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["thinking"], {"type": "disabled"})

    def test_response_content_supports_text_parts(self):
        payload = {
            "choices": [{
                "message": {"content": [{"type": "text", "text": "hello"}, {"text": " world"}]},
                "finish_reason": "length",
            }],
        }

        self.assertEqual(_response_content(payload), ("hello world", True))

    def test_response_content_rejects_wrong_shape(self):
        with self.assertRaisesRegex(ValueError, "choices"):
            _response_content({"message": "not-openai-compatible"})


if __name__ == "__main__":
    unittest.main()
