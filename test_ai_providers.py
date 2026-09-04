import unittest

from ai_providers import (
    CUSTOM_PROVIDER,
    PROVIDER_PRESETS,
    derive_models_url,
    ensure_chat_completions_url,
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

    def test_derives_models_url_from_base_endpoint(self):
        # 与 /chat/completions 自动补全一致：基础地址同样可以推导模型列表 URL
        self.assertEqual(
            derive_models_url("https://ark.cn-beijing.volces.com/api/coding/v3"),
            "https://ark.cn-beijing.volces.com/api/coding/v3/models",
        )
        self.assertEqual(
            derive_models_url("http://example.test/custom/generate"),
            "http://example.test/custom/generate/models",
        )

    def test_rejects_unknown_or_non_http_endpoint(self):
        # 非 HTTP(S) 端点无法推导
        self.assertEqual(derive_models_url("file:///v1/chat/completions"), "")
        self.assertEqual(derive_models_url(""), "")

    def test_auto_completes_chat_completions_suffix(self):
        self.assertEqual(
            ensure_chat_completions_url("https://ark.cn-beijing.volces.com/api/coding/v3"),
            "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        )
        self.assertEqual(
            ensure_chat_completions_url("https://example.test/v1/chat/completions"),
            "https://example.test/v1/chat/completions",
        )
        self.assertEqual(
            ensure_chat_completions_url("https://example.test/v1/"),
            "https://example.test/v1/chat/completions",
        )
        self.assertEqual(
            ensure_chat_completions_url("https://example.test"),
            "https://example.test/chat/completions",
        )
        self.assertEqual(
            ensure_chat_completions_url("https://example.test/api/v3?key=1"),
            "https://example.test/api/v3/chat/completions?key=1",
        )
        self.assertEqual(ensure_chat_completions_url(""), "")
        self.assertEqual(ensure_chat_completions_url("   "), "")


if __name__ == "__main__":
    unittest.main()
