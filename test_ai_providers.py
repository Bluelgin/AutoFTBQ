import unittest

from ai_providers import (
    CUSTOM_PROVIDER,
    PROVIDER_PRESETS,
    derive_models_url,
    normalize_provider,
    resolve_provider_model,
    select_provider_model,
)


class AIProviderTests(unittest.TestCase):
    def test_migrates_legacy_provider_names(self):
        self.assertEqual(normalize_provider("deepseek"), "DeepSeek")
        self.assertEqual(normalize_provider("custom"), CUSTOM_PROVIDER)

    def test_presets_use_current_default_models(self):
        expected = {
            "DeepSeek": "deepseek-v4-flash",
            "OpenAI": "gpt-4o",
            "Gemini": "gemini-2.5-flash",
            "Moonshot": "kimi-k2.6",
            "Zhipu": "glm-5.2",
            "Qwen": "qwen3.7-plus",
            "SiliconFlow": "deepseek-ai/DeepSeek-V4-Flash",
        }

        self.assertEqual(
            {provider: PROVIDER_PRESETS[provider]["model"] for provider in expected},
            expected,
        )

    def test_migrates_only_known_old_preset_models(self):
        self.assertEqual(resolve_provider_model("DeepSeek", "deepseek-chat"), "deepseek-v4-flash")
        self.assertEqual(resolve_provider_model("Moonshot", "moonshot-v1-8k"), "kimi-k2.6")
        self.assertEqual(resolve_provider_model("Zhipu", "glm-4"), "glm-5.2")
        self.assertEqual(resolve_provider_model("Qwen", "qwen-plus"), "qwen3.7-plus")
        self.assertEqual(
            resolve_provider_model("SiliconFlow", "deepseek-ai/DeepSeek-V3"),
            "deepseek-ai/DeepSeek-V4-Flash",
        )
        self.assertEqual(resolve_provider_model("DeepSeek", "my-private-model"), "my-private-model")
        self.assertEqual(resolve_provider_model(CUSTOM_PROVIDER, "custom-model"), "custom-model")

    def test_model_selection_prefers_current_then_provider_default(self):
        models = ["aaa-embedding", "deepseek-v4-flash", "zzz-vision"]

        self.assertEqual(
            select_provider_model("DeepSeek", "zzz-vision", models),
            "zzz-vision",
        )
        self.assertEqual(
            select_provider_model("DeepSeek", "removed-model", models),
            "deepseek-v4-flash",
        )
        self.assertEqual(
            select_provider_model("DeepSeek", "removed-model", ["fallback-model"]),
            "fallback-model",
        )

    def test_derives_models_url_without_copying_query_parameters(self):
        url = "https://example.test/v1/chat/completions/?token=hidden"

        self.assertEqual(derive_models_url(url), "https://example.test/v1/models")

    def test_rejects_unknown_or_non_http_endpoint(self):
        self.assertEqual(derive_models_url("http://example.test/custom/generate"), "")
        self.assertEqual(derive_models_url("file:///v1/chat/completions"), "")


if __name__ == "__main__":
    unittest.main()
