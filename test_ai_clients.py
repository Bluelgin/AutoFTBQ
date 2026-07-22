import unittest

from ai_clients import GenericOpenAIClient, _response_content, create_chat_client


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
