import sys
import types
import unittest
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    req = types.ModuleType("requests")

    class _ReqExc(Exception):
        pass

    class _Conn(_ReqExc):
        pass

    class _Timeout(_ReqExc):
        pass

    req.RequestException = _ReqExc
    req.ConnectionError = _Conn
    req.Timeout = _Timeout
    req.exceptions = types.SimpleNamespace(
        RequestException=_ReqExc, ConnectionError=_Conn,
        Timeout=_Timeout, JSONDecodeError=ValueError,
    )
    sys.modules["requests"] = req

from mod_info import (
    build_links,
    curseforge_search_url,
    fetch_mod_info,
    format_mod_info,
    ftbwiki_search_url,
    mcmod_class_url,
    mcmod_search_url,
    moddedminecraftwiki_search_url,
    modrinth_detail_url,
    modrinth_search_url,
    planetminecraft_search_url,
    web_search_url,
)


class ModInfoLinkTests(unittest.TestCase):
    def test_search_links(self):
        self.assertEqual(mcmod_search_url("create"), "https://search.mcmod.cn/s?key=create")
        self.assertEqual(modrinth_search_url("create"), "https://modrinth.com/mods?q=create")
        self.assertEqual(
            curseforge_search_url("create"),
            "https://www.curseforge.com/minecraft/search?search=create",
        )

    def test_extra_platform_search_links(self):
        self.assertEqual(
            ftbwiki_search_url("create"),
            "https://ftb.fandom.com/wiki/Special:Search?query=create",
        )
        self.assertEqual(
            moddedminecraftwiki_search_url("create"),
            "https://moddedminecraft.wiki/w/Special:Search?search=create",
        )
        self.assertEqual(
            planetminecraft_search_url("create"),
            "https://www.planetminecraft.com/mods/?q=create",
        )
        self.assertIn("baidu.com", web_search_url("create"))

    def test_class_and_slug_links(self):
        self.assertEqual(mcmod_class_url("12345"), "https://www.mcmod.cn/class/12345.html")
        self.assertEqual(mcmod_class_url(""), "")
        self.assertEqual(modrinth_detail_url("create"), "https://modrinth.com/mod/create")

    def test_build_links_prefers_detail_pages(self):
        links = build_links("create", mcmod_class_id="12345", modrinth_slug="create")
        self.assertEqual(links["mcmod"], "https://www.mcmod.cn/class/12345.html")
        self.assertEqual(links["modrinth"], "https://modrinth.com/mod/create")
        self.assertIn("curseforge", links)
        self.assertIn("ftbwiki", links)
        self.assertIn("moddedminecraftwiki", links)
        self.assertIn("planetminecraft", links)
        self.assertIn("websearch", links)

    def test_build_links_prefers_detail_pages(self):
        links = build_links("create", mcmod_class_id="12345", modrinth_slug="create")
        self.assertEqual(links["mcmod"], "https://www.mcmod.cn/class/12345.html")
        self.assertEqual(links["modrinth"], "https://modrinth.com/mod/create")
        self.assertIn("curseforge", links)


class ModInfoFetchTests(unittest.TestCase):
    @patch("mod_info._wiki.fetch_mod_wiki", return_value=None)
    @patch("mod_info._mrc._get_session", side_effect=RuntimeError("offline"))
    def test_local_fallback(self, _sess, _wiki):
        info = fetch_mod_info("create", local_name="Create Mod", local_category="tech")
        self.assertEqual(info["name"], "Create Mod")
        self.assertEqual(info["platform"], "local")
        self.assertEqual(info["category"], "tech")
        self.assertIn("mcmod", info["links"])
        # MOD_DB 收录的 mod 会补全名称/分类
        info2 = fetch_mod_info("tconstruct", local_name="", local_category="")
        self.assertEqual(info2["name"], "Tinkers Construct")
        self.assertEqual(info2["category"], "tech")

    @patch("mod_info._wiki.fetch_mod_wiki", return_value={
        "name": "机械动力", "class_id": "2949", "guide_text": "一个科技模组",
    })
    def test_mcmod_source(self, _wiki):
        info = fetch_mod_info("create", local_name="Create")
        self.assertEqual(info["platform"], "mcmod")
        self.assertEqual(info["name"], "机械动力")
        self.assertEqual(info["guide"], "一个科技模组")
        self.assertEqual(info["links"]["mcmod"], "https://www.mcmod.cn/class/2949.html")

    @patch("mod_info._wiki.fetch_mod_wiki", return_value=None)
    @patch("mod_info._mrc._get_session")
    def test_modrinth_source(self, _sess, _wiki):
        resp = types.SimpleNamespace(status_code=200)
        resp.json = lambda: {
            "title": "Create", "description": "A tech mod", "categories": ["technology"],
            "downloads": 123456, "slug": "create",
            "game_versions": ["1.21.1", "1.21", "1.20.6", "1.20.1"],
            "loaders": ["forge", "fabric", "neoforge"],
        }
        _sess.return_value.get.return_value = resp
        info = fetch_mod_info("create", local_name="Create")
        self.assertEqual(info["platform"], "modrinth")
        self.assertEqual(info["name"], "Create")
        self.assertEqual(info["summary"], "A tech mod")
        self.assertEqual(info["downloads"], 123456)
        self.assertEqual(info["category"], "tech")
        self.assertEqual(info["links"]["modrinth"], "https://modrinth.com/mod/create")
        self.assertEqual(info["game_versions"][:2], ["1.21.1", "1.21"])
        self.assertEqual(info["loaders"], ["forge", "fabric", "neoforge"])

    @patch("mod_info._wiki.fetch_mod_wiki", return_value=None)
    @patch("mod_info._mrc._get_session")
    def test_modrinth_search_fallback(self, _sess, _wiki):
        session = _sess.return_value
        session.get.side_effect = [
            types.SimpleNamespace(status_code=404, json=lambda: {}),
            types.SimpleNamespace(status_code=200, json=lambda: {
                "hits": [{
                    "title": "Create", "description": "Found by search",
                    "categories": ["technology"], "downloads": 10, "slug": "create",
                }],
            }),
        ]
        info = fetch_mod_info("creat", local_name="")
        self.assertEqual(info["platform"], "modrinth")
        self.assertEqual(info["name"], "Create")
        self.assertEqual(info["summary"], "Found by search")


class ModInfoFormatTests(unittest.TestCase):
    def test_format_contains_key_fields(self):
        info = {
            "mod_id": "create", "name": "Create", "summary": "A tech mod", "guide": "",
            "category": "tech", "platform": "modrinth", "downloads": 123456,
            "game_versions": ["1.21.1", "1.21", "1.20.1"],
            "loaders": ["forge", "fabric"],
            "links": {
                "mcmod": "https://search.mcmod.cn/s?key=create",
                "modrinth": "https://modrinth.com/mod/create",
                "curseforge": "https://www.curseforge.com/minecraft/search?search=create",
                "mcmod_search": "https://search.mcmod.cn/s?key=create",
                "ftbwiki": "https://ftb.fandom.com/wiki/Special:Search?query=create",
                "moddedminecraftwiki": "https://moddedminecraft.wiki/w/Special:Search?search=create",
                "planetminecraft": "https://www.planetminecraft.com/mods/?q=create",
                "websearch": "https://www.baidu.com/s?wd=create%20mod",
            },
        }
        text = format_mod_info(info)
        self.assertIn("Create", text)
        self.assertIn("create", text)
        self.assertIn("科技", text)  # tech -> 科技
        self.assertIn("Modrinth", text)
        self.assertIn("A tech mod", text)
        self.assertIn("123,456", text)
        self.assertIn("支持 MC 版本: 1.21.1, 1.21, 1.20.1", text)
        self.assertIn("加载器: Forge, Fabric", text)
        self.assertIn("FTB Wiki", text)
        self.assertIn("ModdedMC Wiki", text)
        self.assertIn("Planet Minecraft", text)

    def test_format_local_fallback_message(self):
        info = {
            "mod_id": "unknownmod", "name": "UnknownMod", "summary": "", "guide": "",
            "category": "", "platform": "local", "downloads": 0,
            "links": {"mcmod": "https://search.mcmod.cn/s?key=unknownmod"},
        }
        text = format_mod_info(info)
        self.assertIn("本地资料", text)
        self.assertIn("未能从平台获取简介", text)


if __name__ == "__main__":
    unittest.main()
