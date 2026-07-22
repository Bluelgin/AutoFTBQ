import unittest

from ai_providers import CUSTOM_PROVIDER, derive_models_url, normalize_provider


class AIProviderTests(unittest.TestCase):
    def test_migrates_legacy_provider_names(self):
        self.assertEqual(normalize_provider("deepseek"), "DeepSeek")
        self.assertEqual(normalize_provider("custom"), CUSTOM_PROVIDER)

    def test_derives_models_url_without_copying_query_parameters(self):
        url = "https://example.test/v1/chat/completions/?token=hidden"

        self.assertEqual(derive_models_url(url), "https://example.test/v1/models")

    def test_rejects_unknown_or_non_http_endpoint(self):
        self.assertEqual(derive_models_url("http://example.test/custom/generate"), "")
        self.assertEqual(derive_models_url("file:///v1/chat/completions"), "")


if __name__ == "__main__":
    unittest.main()
