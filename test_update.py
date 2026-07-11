import json
import sys
import threading
import types
import unittest

import main


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class UpdateTests(unittest.TestCase):
    def _check(self, current, payload):
        calls = []
        done = threading.Event()
        fake_requests = types.ModuleType("requests")
        fake_requests.get = lambda *args, **kwargs: FakeResponse(payload)
        previous = sys.modules.get("requests")
        sys.modules["requests"] = fake_requests
        try:
            main.check_for_update(current, lambda latest, info: (calls.append((latest, info)), done.set()))
            self.assertTrue(done.wait(2), "update callback did not finish")
            return calls[0]
        finally:
            if previous is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = previous

    def test_1_3_1_detects_1_3_2_with_two_urls(self):
        latest, info = self._check("1.3.1", {
            "version": "v1.3.2",
            "github_url": "https://github.com/example/release.exe",
            "quark_url": "https://pan.quark.cn/s/example",
        })

        self.assertEqual(latest, "v1.3.2")
        self.assertEqual(info["github_url"], "https://github.com/example/release.exe")
        self.assertEqual(info["quark_url"], "https://pan.quark.cn/s/example")
        self.assertFalse(info["error"])

    def test_current_version_finishes_without_update(self):
        latest, info = self._check("1.3.2", {"version": "1.3.2"})

        self.assertIsNone(latest)
        self.assertFalse(info["error"])
        self.assertEqual(info["quark_url"], main.QUARK_FALLBACK_URL)

    def test_legacy_quark_download_url_is_not_used_for_github(self):
        latest, info = self._check("1.3.1", {
            "version": "1.3.2",
            "download_url": "https://pan.quark.cn/s/legacy",
        })

        self.assertEqual(latest, "1.3.2")
        self.assertEqual(info["quark_url"], "https://pan.quark.cn/s/legacy")
        self.assertIn("github.com/Bluelgin/AutoFTBQ", info["github_url"])


if __name__ == "__main__":
    unittest.main()
