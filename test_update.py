import json
import sys
import threading
import time
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

    def test_uses_master_branch_update_file(self):
        self.assertIn("/master/update.json", main.UPDATE_URL)

    def test_falls_back_when_primary_update_source_fails(self):
        calls = []
        done = threading.Event()
        fake_requests = types.ModuleType("requests")

        def get(url, **kwargs):
            calls.append(url)
            if url == main.UPDATE_URL:
                raise ConnectionError("raw GitHub unavailable")
            return FakeResponse({"version": "1.4.0"})

        fake_requests.get = get
        previous = sys.modules.get("requests")
        sys.modules["requests"] = fake_requests
        try:
            result = []
            main.check_for_update(
                "1.3.5",
                lambda latest, info: (result.append((latest, info)), done.set()),
            )
            self.assertTrue(done.wait(2), "fallback update callback did not finish")
        finally:
            if previous is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = previous

        latest, info = result[0]
        self.assertEqual(latest, "1.4.0")
        self.assertEqual(calls[:2], list(main.UPDATE_URLS))
        self.assertEqual(info["source"], main.UPDATE_URLS[1])
        self.assertFalse(info["error"])

    def test_github_release_api_is_final_fallback(self):
        done = threading.Event()
        fake_requests = types.ModuleType("requests")

        def get(url, **kwargs):
            if url != main.GITHUB_RELEASE_API:
                raise ConnectionError("metadata mirror unavailable")
            return FakeResponse({
                "tag_name": "v1.4.1",
                "html_url": "https://github.com/example/releases/tag/v1.4.1",
                "assets": [{
                    "name": "AutoFTBQ.exe",
                    "browser_download_url": "https://github.com/example/AutoFTBQ.exe",
                }],
                "body": "Fix update checking",
            })

        fake_requests.get = get
        previous = sys.modules.get("requests")
        sys.modules["requests"] = fake_requests
        try:
            result = []
            main.check_for_update(
                "1.3.5",
                lambda latest, info: (result.append((latest, info)), done.set()),
            )
            self.assertTrue(done.wait(2), "GitHub API fallback callback did not finish")
        finally:
            if previous is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = previous

        latest, info = result[0]
        self.assertEqual(latest, "v1.4.1")
        self.assertEqual(info["source"], main.GITHUB_RELEASE_API)
        self.assertEqual(info["github_url"], "https://github.com/example/AutoFTBQ.exe")
        self.assertEqual(info["quark_url"], main.QUARK_FALLBACK_URL)

    def test_ui_poll_delivers_worker_result_on_ui_thread(self):
        app = main.App.__new__(main.App)
        app._update_request_id = 4
        app._update_checking = True
        app._pending_update_result = (4, "1.4.0", {"error": ""})
        delivered = []
        app._on_update_result = lambda latest, info: delivered.append((latest, info))

        main.App._poll_update_result(app, 4, time.monotonic() + 1)

        self.assertEqual(delivered, [("1.4.0", {"error": ""})])
        self.assertIsNone(app._pending_update_result)

    def test_ui_poll_exits_with_clickable_timeout(self):
        class FakeLabel:
            def __init__(self):
                self.values = {}

            def config(self, **kwargs):
                self.values.update(kwargs)

        app = main.App.__new__(main.App)
        app._update_request_id = 9
        app._update_checking = True
        app._update_checked = False
        app._pending_update_result = None
        app.update_label = FakeLabel()

        main.App._poll_update_result(app, 9, time.monotonic() - 1)

        self.assertFalse(app._update_checking)
        self.assertTrue(app._update_checked)
        self.assertIn("超时", app.update_label.values["text"])


if __name__ == "__main__":
    unittest.main()
