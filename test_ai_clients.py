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


class FakeToolCallResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "search_items",
                            "arguments": '{"namespace":"create","query":"press"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }


class FakeManyToolCallsResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": f"call_{index}",
                        "type": "function",
                        "function": {
                            "name": "search_items",
                            "arguments": '{"namespace":"create","query":"gear"}',
                        },
                    } for index in range(8)],
                },
                "finish_reason": "tool_calls",
            }],
        }


class FakeErrorResponse:
    status_code = 400
    text = "tools unsupported"

    def json(self):
        return {"error": self.text}


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

    @patch("ai_clients.requests.post", side_effect=[FakeToolCallResponse(), FakeChatResponse()])
    def test_tool_loop_executes_handler_and_returns_final_content(self, post):
        client = GenericOpenAIClient("secret", "https://example.test/chat", "model")
        calls = []

        content, truncated = client.chat_with_tools(
            [{"role": "user", "content": "generate"}],
            [{"type": "function", "function": {"name": "search_items", "parameters": {}}}],
            lambda name, arguments: calls.append((name, arguments)) or "[]",
        )

        self.assertEqual(content, "{}")
        self.assertFalse(truncated)
        self.assertEqual(calls[0][0], "search_items")
        second_messages = post.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(second_messages[-1]["role"], "tool")

    @patch("ai_clients.requests.post", side_effect=[FakeManyToolCallsResponse(), FakeChatResponse()])
    def test_tool_loop_keeps_bounded_calls_and_results_in_sync(self, post):
        client = GenericOpenAIClient("secret", "https://example.test/chat", "model")
        calls = []

        client.chat_with_tools(
            [{"role": "user", "content": "generate"}],
            [{"type": "function", "function": {"name": "search_items", "parameters": {}}}],
            lambda name, arguments: calls.append((name, arguments)) or "[]",
        )

        second_messages = post.call_args_list[1].kwargs["json"]["messages"]
        assistant = next(message for message in second_messages if message.get("role") == "assistant")
        tool_results = [message for message in second_messages if message.get("role") == "tool"]
        self.assertEqual(len(assistant["tool_calls"]), 6)
        self.assertEqual(len(tool_results), 6)
        self.assertEqual(len(calls), 6)

    @patch("ai_clients.requests.post", side_effect=[FakeToolCallResponse(), FakeChatResponse()])
    def test_tool_loop_final_synthesis_removes_tools(self, post):
        client = GenericOpenAIClient("secret", "https://example.test/chat", "model")

        client.chat_with_tools(
            [{"role": "user", "content": "generate"}],
            [{"type": "function", "function": {"name": "search_items", "parameters": {}}}],
            lambda *_: "[]",
            max_rounds=1,
        )

        final_payload = post.call_args_list[1].kwargs["json"]
        self.assertNotIn("tools", final_payload)
        self.assertNotIn("tool_choice", final_payload)
        self.assertIn("Stop calling tools", final_payload["messages"][-1]["content"])

    @patch("ai_clients.requests.post", side_effect=[FakeErrorResponse(), FakeChatResponse()])
    def test_tool_rejection_falls_back_and_is_cached(self, post):
        client = GenericOpenAIClient("secret", "https://example.test/chat", "model")

        self.assertEqual(
            client.chat_with_tools(
                [{"role": "user", "content": "generate"}],
                [{"type": "function", "function": {"name": "search_items", "parameters": {}}}],
                lambda *_: "[]",
            )[0],
            "{}",
        )

        self.assertFalse(client._tool_support)
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
