import unittest
from unittest.mock import Mock, patch

import ollama_adapter


class OllamaAdapterTests(unittest.TestCase):
    def test_detection_rejects_non_object_response_without_attribute_error(self):
        response = Mock(status_code=200)
        response.json.return_value = "old-or-invalid-response"

        with patch("ollama_adapter.requests.get", return_value=response):
            self.assertEqual(ollama_adapter.check_ollama_available(), (False, []))

    def test_chat_reports_clear_error_for_non_object_response(self):
        response = Mock(status_code=200)
        response.json.return_value = "invalid-response"
        client = ollama_adapter.OllamaClient("test-model")

        with patch("ollama_adapter.requests.post", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "响应不是 JSON 对象"):
                client.chat([{"role": "user", "content": "hello"}])

    def test_chat_returns_valid_ollama_text(self):
        response = Mock(status_code=200)
        response.json.return_value = {"response": "hello", "done": True}
        client = ollama_adapter.OllamaClient("test-model")

        with patch("ollama_adapter.requests.post", return_value=response):
            self.assertEqual(
                client.chat([{"role": "user", "content": "hello"}]),
                ("hello", False),
            )


if __name__ == "__main__":
    unittest.main()
