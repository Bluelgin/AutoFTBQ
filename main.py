#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoFTBQ - MC FTB Quest Book Generator"""

import os, sys, json, queue, subprocess, threading, traceback, webbrowser, time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from instance_resolver import application_dir, resolve_instance, suggested_output_dir

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
APP_DIR = application_dir(SCRIPT_DIR)

APP_NAME = "AutoFTBQ"; VERSION = "1.3.9"; AUTHOR = "Taki"
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

AI_AVAILABLE = False; AI_IMPORT_ERROR = ""
scan_mod_folder = None; generate_quest_book = None
build_full_prompt = None; import_json_to_snbt = None
normalize_provider = None; resolve_provider_model = None; select_provider_model = None
fetch_provider_models = None; derive_models_url = None; PROVIDER_PRESETS = {}

LANG = "zh"

# Ollama状态
ollama_available = False
ollama_models = []
ollama_best_model = None

CAT_LABEL = {"vanilla":"原版","tech":"科技","magic":"魔法","world":"维度/Boss","mob":"生物","utility":"辅助","food":"食物","decor":"装饰","unknown":"未知"}

# ── 版本检测 ──
UPDATE_URL = "https://raw.githubusercontent.com/Bluelgin/AutoFTBQ/master/update.json"
UPDATE_URLS = (
    UPDATE_URL,
    "https://cdn.jsdelivr.net/gh/Bluelgin/AutoFTBQ@master/update.json",
)
GITHUB_RELEASE_API = "https://api.github.com/repos/Bluelgin/AutoFTBQ/releases/latest"
QUARK_FALLBACK_URL = "https://pan.quark.cn/s/25387b63a76c"

def _parse_version(ver_str):
    try:
        parts = str(ver_str).strip().lstrip("vV").split(".")
        return tuple(int(x) for x in parts[:3])
    except Exception:
        return (0,)

def check_for_update(current_version, callback=None):
    """Asynchronously check for an update and always finish with one callback."""
    def _run():
        latest = None
        info = {
            "github_url": "",
            "quark_url": "",
            "changelog": "",
            "error": "",
            "source": "",
        }
        try:
            import requests
            errors = []
            data = None
            sources = UPDATE_URLS + (GITHUB_RELEASE_API,)
            for source in sources:
                try:
                    response = requests.get(
                        source,
                        params={"_": str(int(time.time()))},
                        timeout=(2, 4),
                        headers={
                            "Accept": "application/vnd.github+json",
                            "Cache-Control": "no-cache",
                            "User-Agent": "AutoFTBQ",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("更新源返回的不是 JSON 对象")
                    if source == GITHUB_RELEASE_API:
                        assets = payload.get("assets", [])
                        exe_url = ""
                        if isinstance(assets, list):
                            for asset in assets:
                                if not isinstance(asset, dict):
                                    continue
                                name = str(asset.get("name", "")).lower()
                                if name.endswith(".exe"):
                                    exe_url = str(asset.get("browser_download_url", ""))
                                    break
                        payload = {
                            "version": payload.get("tag_name", ""),
                            "github_url": exe_url or payload.get("html_url", ""),
                            "quark_url": QUARK_FALLBACK_URL,
                            "changelog": payload.get("body", ""),
                        }
                    if not str(payload.get("version", "")).strip():
                        raise ValueError("更新源缺少版本号")
                    data = payload
                    info["source"] = source
                    break
                except Exception as source_error:
                    errors.append(f"{source}: {source_error}")
            if data is None:
                raise RuntimeError("所有更新源均不可用；" + "；".join(errors))

            latest = str(data.get("version", "")).strip()
            legacy_url = str(data.get("download_url", "")).strip()
            info["github_url"] = str(data.get("github_url", "")).strip()
            info["quark_url"] = str(data.get("quark_url", "")).strip()
            info["changelog"] = str(data.get("changelog", "")).strip()
            # Backward compatibility with both old Quark and old GitHub schemas.
            if legacy_url:
                if "pan.quark.cn" in legacy_url and not info["quark_url"]:
                    info["quark_url"] = legacy_url
                elif not info["github_url"]:
                    info["github_url"] = legacy_url
            if not info["github_url"]:
                info["github_url"] = "https://github.com/Bluelgin/AutoFTBQ/releases/latest"
            if not info["quark_url"]:
                info["quark_url"] = QUARK_FALLBACK_URL
            if not latest or _parse_version(latest) <= _parse_version(current_version):
                latest = None
        except Exception as exc:
            info["error"] = str(exc)
            latest = None
        if callback:
            try:
                callback(latest, info)
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()

T = {
    "zh": {
        "title": "AutoFTBQ - MC FTB任务书生成器",
        "subtitle": "选择 Mod → AI 生成完整任务指南",
        "subtitle_api": "API 模式 — DeepSeek / Ollama 自动生成",
        "subtitle_import": "导入模式 — 网页AI生成后粘贴JSON",
        "api_key": "API Key", "api_desc": "输入 API Key",
        "mod_folder": "整合包或 Mod 文件夹", "mod_desc": "选择整合包根目录或包含 .jar / .zip Mod 的文件夹",
        "browse": "浏览", "show": "显示", "hide": "隐藏",
        "select_mods": "选择 Mod",
        "save_config": "保存配置", "generate": "生成任务书", "generating": "生成中...",
        "ready": "就绪 - 请选择 Mod 并填写 API Key",
        "config_ready": "配置就绪 - 点击生成",
        "deps_missing": "请安装依赖",
        "enter_api": "请输入 API Key",
        "select_mod": "请选择 Mod 文件夹",
        "starting": "启动中...",
        "confirm_title": "确认生成",
        "confirm_msg": "已选中 {} 个Mod，将生成丰富的任务指南。\n约需2-4分钟。继续？",
        "success_title": "生成成功！",
        "success_msg": "任务书已生成到:\n{}\n\n打开目录？",
        "failed": "生成失败: {}", "gen_failed": "生成失败",
        "scanning": "扫描中", "found_mods": "检测到 {} 个Mod文件",
        "no_mods": "未检测到.jar/.zip", "no_mods_folder": "未找到Mod文件",
        "dir_error": "无法读取",
        "saved": "配置已保存!", "saved_info": "配置保存成功!",
        "preparing": "准备生成...",
        "dep_error_title": "缺少依赖",
        "dep_msg": "缺少requests模块。请运行:\npython -m pip install requests\n然后重启。",
        "close_confirm": "生成中，关闭将中断。确定?",
        "author_line": "作者: Taki", "powered": "Powered by DeepSeek AI",
        "lang": "EN",
    },
    "en": {
        "title": "AutoFTBQ - FTB Quest Generator",
        "subtitle": "Select Mods → AI generates quest guide",
        "subtitle_api": "API Mode — DeepSeek / Ollama auto-gen",
        "subtitle_import": "Import Mode — paste JSON from web AI",
        "api_key": "API Key", "api_desc": "Enter API Key",
        "mod_folder": "Modpack or Mod Folder", "mod_desc": "Select a modpack root or .jar / .zip folder",
        "browse": "Browse", "show": "Show", "hide": "Hide",
        "select_mods": "Select Mods",
        "save_config": "Save", "generate": "Generate", "generating": "Generating...",
        "ready": "Ready - select Mods and fill API Key",
        "config_ready": "Config ready - click Generate",
        "deps_missing": "Install deps",
        "enter_api": "Enter API Key",
        "select_mod": "Select Mod folder",
        "starting": "Starting...",
        "confirm_title": "Confirm",
        "confirm_msg": "{} mod(s) selected. Generate rich quest guide?\n~2-4 min.",
        "success_title": "Success!",
        "success_msg": "Questbook saved:\n{}\n\nOpen folder?",
        "failed": "Failed: {}", "gen_failed": "Failed",
        "scanning": "Scanning", "found_mods": "{} mod(s) detected",
        "no_mods": "No .jar/.zip", "no_mods_folder": "No mod files found",
        "dir_error": "Cannot read",
        "saved": "Saved!", "saved_info": "Config saved!",
        "preparing": "Preparing...",
        "dep_error_title": "Missing Deps",
        "dep_msg": "Missing requests.\nRun: python -m pip install requests\nThen restart.",
        "close_confirm": "Generation in progress. Close?",
        "author_line": "Author: Taki", "powered": "Powered by DeepSeek AI",
        "lang": "中文",
    },
}

def t(key, *args):
    val = T[LANG].get(key, key)
    return val.format(*args) if args else val

def _check_deps():
    global AI_AVAILABLE, AI_IMPORT_ERROR, scan_mod_folder, generate_quest_book
    global build_full_prompt, import_json_to_snbt
    global normalize_provider, resolve_provider_model, select_provider_model
    global fetch_provider_models, PROVIDER_PRESETS, derive_models_url
    try: import requests
    except ImportError: AI_IMPORT_ERROR = t("dep_msg"); return False
    try:
        import ai_module, importlib
        importlib.reload(ai_module)
        scan_mod_folder = ai_module.scan_mod_folder
        generate_quest_book = ai_module.generate_quest_book
        build_full_prompt = ai_module.build_full_prompt
        import_json_to_snbt = ai_module.import_json_to_snbt
        normalize_provider = ai_module.normalize_provider
        resolve_provider_model = ai_module.resolve_provider_model
        select_provider_model = ai_module.select_provider_model
        fetch_provider_models = ai_module.fetch_provider_models
        derive_models_url = ai_module.derive_models_url
        PROVIDER_PRESETS = ai_module.PROVIDER_PRESETS
        AI_AVAILABLE = True; return True
    except Exception as e: AI_IMPORT_ERROR = str(e); return False

def _mod_matches_query(mod, query):
    query = str(query or "").strip().casefold()
    if not query:
        return True
    category = str(mod.get("category", "unknown"))
    fields = (
        mod.get("mod_name", ""),
        mod.get("mod_id", ""),
        mod.get("filename", ""),
        category,
        CAT_LABEL.get(category, ""),
    )
    return any(query in str(value).casefold() for value in fields)


class ModSelectDialog(tk.Toplevel):
    def __init__(self, parent, mods, selected_filenames=None):
        super().__init__(parent)
        self.title("选择要生成任务书的 Mod")
        self.geometry("680x540")
        self.resizable(False, False)
        self.configure(bg="#ffffff")
        self.result = []
        self._mods = list(mods)
        self._visible_mods = []
        self._selected_filenames = set(selected_filenames or [])
        self._rebuilding = False

        try:
            tk.Label(self, text="勾选要包含在任务书中的 Mod：",
                     font=("Microsoft YaHei", 12, "bold"), bg="#ffffff", fg="#333333").pack(pady=(15, 5))
            tk.Label(self, text=f"检测到 {len(mods)} 个Mod — 请选择需要的Mod（可多选）",
                     font=("Microsoft YaHei", 9), bg="#ffffff", fg="#888888").pack(pady=(0, 10))

            search_frame = tk.Frame(self, bg="#ffffff")
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 8))
            tk.Label(
                search_frame,
                text="搜索 Mod：",
                font=("Microsoft YaHei", 9),
                bg="#ffffff",
                fg="#555555",
            ).pack(side=tk.LEFT)
            self._search_var = tk.StringVar()
            self._search_entry = tk.Entry(
                search_frame,
                textvariable=self._search_var,
                font=("Microsoft YaHei", 10),
                relief=tk.SOLID,
                bd=1,
            )
            self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
            tk.Button(
                search_frame,
                text="清除搜索",
                command=lambda: self._search_var.set(""),
                bg="#eeeeee",
                font=("Microsoft YaHei", 9),
                padx=8,
            ).pack(side=tk.LEFT, padx=(8, 0))

            frame = tk.Frame(self, bg="#ffffff")
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self._lb = tk.Listbox(frame, selectmode="multiple", yscrollcommand=scrollbar.set,
                                  font=("Microsoft YaHei", 9), bg="#ffffff", fg="#333333",
                                  activestyle="none", exportselection=False)
            self._lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=self._lb.yview)
            self._lb.bind("<<ListboxSelect>>", self._on_listbox_select)

            self._count_label = tk.Label(
                self,
                text="",
                font=("Microsoft YaHei", 9),
                bg="#ffffff",
                fg="#666666",
                anchor="w",
            )
            self._count_label.pack(fill=tk.X, padx=20, pady=(0, 8))

            self._search_var.trace_add("write", self._on_search_changed)
            self._rebuild_list()

            btnf = tk.Frame(self, bg="#ffffff")
            btnf.pack(fill=tk.X, pady=(0, 15), padx=20)
            tk.Button(btnf, text="全选当前结果", command=self._select_all, bg="#e0e0e0",
                      font=("Microsoft YaHei", 10), padx=10).pack(side=tk.LEFT)
            tk.Button(btnf, text="清空当前结果", command=self._clear_visible, bg="#eeeeee",
                      font=("Microsoft YaHei", 10), padx=10).pack(side=tk.LEFT, padx=(8, 0))
            tk.Button(btnf, text="确定", command=self._on_ok, bg="#4caf50", fg="#ffffff",
                      font=("Microsoft YaHei", 11, "bold"), padx=30, pady=5).pack(side=tk.RIGHT)
            tk.Button(btnf, text="取消", command=self._on_cancel, bg="#cccccc", fg="#ffffff",
                      font=("Microsoft YaHei", 11), padx=20, pady=5).pack(side=tk.RIGHT, padx=(0, 10))

            self.transient(parent)
            self.grab_set()
            self.protocol("WM_DELETE_WINDOW", self._on_cancel)
            self._center(parent)
            self._search_entry.focus_set()
        except Exception as e:
            messagebox.showerror("错误", f"无法创建Mod选择窗口: {e}")
            self.result = None
            self.destroy()

    def _center(self, parent):
        try:
            self.update_idletasks()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_x(), parent.winfo_y()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
        except Exception:
            pass

    def _sync_visible_selection(self):
        if self._rebuilding:
            return
        selected_indices = set(self._lb.curselection())
        for index, mod in enumerate(self._visible_mods):
            filename = mod.get("filename")
            if index in selected_indices:
                self._selected_filenames.add(filename)
            else:
                self._selected_filenames.discard(filename)

    def _update_count(self):
        self._count_label.config(
            text=f"当前显示 {len(self._visible_mods)} 个  |  已选择 {len(self._selected_filenames)} 个"
        )

    def _rebuild_list(self):
        self._sync_visible_selection()
        query = self._search_var.get()
        self._visible_mods = [
            mod for mod in self._mods if _mod_matches_query(mod, query)
        ]
        self._rebuilding = True
        try:
            self._lb.delete(0, tk.END)
            for index, mod in enumerate(self._visible_mods):
                cat_cn = CAT_LABEL.get(mod.get("category", "unknown"), "?")
                size_mb = mod.get("size", 0) / (1024 * 1024)
                label = f"{mod['mod_name']:30s} [{cat_cn}]  ({size_mb:.1f}MB)"
                self._lb.insert(tk.END, label)
                if mod.get("filename") in self._selected_filenames:
                    self._lb.selection_set(index)
        finally:
            self._rebuilding = False
        self._update_count()

    def _on_search_changed(self, *_):
        self._rebuild_list()

    def _on_listbox_select(self, _event=None):
        self._sync_visible_selection()
        self._update_count()

    def _select_all(self):
        for mod in self._visible_mods:
            self._selected_filenames.add(mod.get("filename"))
        self._lb.selection_set(0, tk.END)
        self._update_count()

    def _clear_visible(self):
        for mod in self._visible_mods:
            self._selected_filenames.discard(mod.get("filename"))
        self._lb.selection_clear(0, tk.END)
        self._update_count()

    def _on_ok(self):
        self._sync_visible_selection()
        if not self._selected_filenames:
            messagebox.showwarning("提示", "请至少选择一个 Mod。")
            return
        self.result = [
            mod["filename"]
            for mod in self._mods
            if mod.get("filename") in self._selected_filenames
        ]
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class ModInfoDialog(tk.Toplevel):
    """MOD 信息窗口：左侧列出已选 MOD，右侧展示来自 MC百科/Modrinth 的详情。"""

    def __init__(self, parent, mods):
        super().__init__(parent)
        self.title("MOD 信息 — MC百科 / Modrinth")
        self.geometry("780x580")
        self.minsize(640, 420)
        self.configure(bg="#ffffff")
        self.mods = list(mods or [])
        self._current = None
        self._request_id = 0
        self._fetching = False

        try:
            df = ("Microsoft YaHei", 10)
            sf = ("Microsoft YaHei", 9)

            body = tk.Frame(self, bg="#ffffff")
            body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 8))

            # ── 左侧：已选 MOD 列表 ──
            left = tk.Frame(body, bg="#ffffff", width=280)
            left.pack(side=tk.LEFT, fill=tk.Y)
            left.pack_propagate(False)
            tk.Label(left, text="已选 MOD（点击查看详情）", font=("Microsoft YaHei", 10, "bold"),
                     fg="#333333", bg="#ffffff").pack(anchor=tk.W, pady=(0, 6))
            list_host = tk.Frame(left, bg="#ffffff")
            list_host.pack(fill=tk.BOTH, expand=True)
            scrollbar = tk.Scrollbar(list_host)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.listbox = tk.Listbox(
                list_host, yscrollcommand=scrollbar.set, font=sf,
                bg="#ffffff", fg="#333333", activestyle="none",
                exportselection=False, bd=1, relief=tk.SOLID,
            )
            self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=self.listbox.yview)
            self.listbox.bind("<<ListboxSelect>>", self._on_select)

            # ── 右侧：详情区 ──
            right = tk.Frame(body, bg="#ffffff")
            right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
            self.detail_text = tk.Text(
                right, font=df, bg="#fafafa", fg="#333333",
                bd=1, relief=tk.SOLID, wrap=tk.WORD, state=tk.DISABLED,
            )
            self.detail_text.pack(fill=tk.BOTH, expand=True)

            # ── 底部按钮 ──
            btnf = tk.Frame(self, bg="#ffffff")
            btnf.pack(fill=tk.X, padx=14, pady=(0, 12))
            self.status_label = tk.Label(btnf, text="", font=sf, fg="#888888", bg="#ffffff")
            self.status_label.pack(side=tk.LEFT)
            self.open_btn = tk.Button(
                btnf, text="🌐 打开 MC百科", command=self._open_platform,
                bg="#4a90d9", fg="#ffffff", font=sf, bd=0,
                cursor="hand2", activebackground="#357abd", activeforeground="#ffffff",
                padx=14, pady=5, state=tk.DISABLED,
            )
            self.open_btn.pack(side=tk.RIGHT)
            tk.Button(
                btnf, text="关闭", command=self.destroy, font=sf,
                bg="#cccccc", fg="#ffffff", bd=0, padx=18, pady=5,
            ).pack(side=tk.RIGHT, padx=(0, 10))

            for mod in self.mods:
                name = mod.get("mod_name", "?")
                mod_id = mod.get("mod_id", "?")
                self.listbox.insert(tk.END, f"{name}  ({mod_id})")

            self.transient(parent)
            self._center(parent)
            if self.mods:
                self.listbox.selection_set(0)
                self._on_select()
        except Exception as exc:
            messagebox.showerror("错误", f"无法创建 MOD 信息窗口: {exc}")
            self.destroy()

    def _center(self, parent):
        try:
            self.update_idletasks()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_x(), parent.winfo_y()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
        except Exception:
            pass

    def _set_detail(self, text):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state=tk.DISABLED)

    def _on_select(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        mod = self.mods[sel[0]]
        self._current = mod
        self.open_btn.config(state=tk.NORMAL)
        # 先展示本地已知信息，同时后台异步获取平台详情
        mod_id = mod.get("mod_id", "")
        self._set_detail(
            f"正在获取 {mod.get('mod_name', mod_id)} 的信息...\n\n"
            f"Mod ID: {mod_id}\n"
            "（将尝试从 MC百科、Modrinth 获取，请稍候）"
        )
        self.status_label.config(text="查询中...", fg="#ff9800")
        self._request_id += 1
        request_id = self._request_id
        threading.Thread(
            target=self._fetch_thread,
            args=(request_id, mod),
            daemon=True,
        ).start()

    def _fetch_thread(self, request_id, mod):
        try:
            import mod_info
            info = mod_info.fetch_mod_info(
                mod.get("mod_id", ""),
                local_name=mod.get("mod_name", ""),
                local_category=mod.get("category", ""),
            )
            text = mod_info.format_mod_info(info)
        except Exception as exc:
            info = None
            text = (
                f"【{mod.get('mod_name', '?')}】\n"
                f"Mod ID: {mod.get('mod_id', '?')}\n\n"
                f"查询失败: {exc}\n\n"
                "可点击下方“打开 MC百科”手动查询。"
            )
        self.after(0, self._show_info, request_id, info, text)

    def _show_info(self, request_id, info, text):
        if request_id != self._request_id:
            return  # 用户已切换到其他 MOD
        self._set_detail(text)
        if info and isinstance(info, dict):
            platform = (info.get("platform") or "")
            if platform == "mcmod":
                self.status_label.config(text="来源: MC百科", fg="#4caf50")
            elif platform == "modrinth":
                self.status_label.config(text="来源: Modrinth", fg="#4caf50")
            else:
                self.status_label.config(text="未获取到平台资料，可打开链接查询", fg="#c77700")
            self._last_links = info.get("links") or {}
        else:
            self._last_links = {}
            self.status_label.config(text="查询失败", fg="#f44336")

    def _open_platform(self):
        """打开当前 MOD 的平台页面（优先 MC百科详情页，其次搜索页）。"""
        if self._current is None:
            return
        links = getattr(self, "_last_links", None)
        url = ""
        if links and links.get("mcmod"):
            url = links["mcmod"]
        else:
            mod_id = self._current.get("mod_id", "")
            url = f"https://search.mcmod.cn/s?key={mod_id}"
        try:
            webbrowser.open(url)
        except Exception:
            subprocess.Popen(["explorer", url], shell=True)


class ModeSelectDialog(tk.Toplevel):
    """启动时让用户选择工作模式"""
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"{APP_NAME} — 选择工作模式")
        self.geometry("540x520")
        self.resizable(False, False)
        self.configure(bg="#ffffff")
        self.result = None  # "api" or "import"

        try:
            df = ("Microsoft YaHei", 10)

            tk.Label(self, text="欢迎使用 AutoFTBQ",
                     font=("Microsoft YaHei", 18, "bold"), fg="#1a1a1a", bg="#ffffff").pack(pady=(25, 5))
            tk.Label(self, text="请选择工作模式：",
                     font=("Microsoft YaHei", 11), fg="#888888", bg="#ffffff").pack(pady=(0, 20))

            # API 模式卡片
            card1 = tk.Frame(self, bg="#f5f8ff", bd=1, relief=tk.SOLID, padx=18, pady=14)
            card1.pack(fill=tk.X, padx=30, pady=(0, 10))
            card1.bind("<Button-1>", lambda e: self._select("api"))
            for child in card1.winfo_children():
                child.bind("<Button-1>", lambda e: self._select("api"))
            tk.Label(card1, text="🤖  API 自动生成", font=("Microsoft YaHei", 13, "bold"),
                     fg="#1a1a1a", bg="#f5f8ff").pack(anchor=tk.W)
            tk.Label(card1, text="填写 API Key 或使用本地 Ollama，"
                     "一键自动生成任务书 JSON 并转换为 SNBT",
                     font=df, fg="#666666", bg="#f5f8ff", wraplength=400, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 6))
            tk.Button(card1, text="选择 API 模式 →", font=("Microsoft YaHei", 10, "bold"),
                      command=lambda: self._select("api"), bg="#4a90d9", fg="#ffffff",
                      bd=0, relief=tk.FLAT, cursor="hand2", padx=20, pady=6).pack(anchor=tk.W)

            # 导入模式卡片
            card2 = tk.Frame(self, bg="#f5fff5", bd=1, relief=tk.SOLID, padx=18, pady=14)
            card2.pack(fill=tk.X, padx=30, pady=(0, 10))
            card2.bind("<Button-1>", lambda e: self._select("import"))
            for child in card2.winfo_children():
                child.bind("<Button-1>", lambda e: self._select("import"))
            tk.Label(card2, text="📄  导入 JSON", font=("Microsoft YaHei", 13, "bold"),
                     fg="#1a1a1a", bg="#f5fff5").pack(anchor=tk.W)
            tk.Label(card2, text="保存「提示词+物品ID」文件 → 上传至网页 AI → "
                     "粘贴返回的 JSON → 自动校验并转为 SNBT",
                     font=df, fg="#666666", bg="#f5fff5", wraplength=400, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 4))
            tk.Label(card2, text="⚠ 仅建议Mod数量较少（100以内）的整合包使用此模式，"
                     "否则可能导致生成内容缺失",
                     font=("Microsoft YaHei", 8), fg="#e65100", bg="#f5fff5",
                     wraplength=400, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))
            tk.Button(card2, text="选择导入模式 →", font=("Microsoft YaHei", 10, "bold"),
                      command=lambda: self._select("import"), bg="#4caf50", fg="#ffffff",
                      bd=0, relief=tk.FLAT, cursor="hand2", padx=20, pady=6).pack(anchor=tk.W)

            self.transient(parent)
            self.grab_set()
            self.protocol("WM_DELETE_WINDOW", self._on_close)

            # 居中
            self.update_idletasks()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_x(), parent.winfo_y()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.result = "api"
            self.destroy()

    def _select(self, mode):
        self.result = mode
        self.destroy()

    def _on_close(self):
        self.result = "api"  # 默认API模式
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION} - {AUTHOR}")

        # 先给 root 一个合理尺寸，让弹窗能正常居中
        self.root.geometry("540x520")
        self.root.update_idletasks()

        # 启动即询问模式
        mode_dlg = ModeSelectDialog(self.root)
        self.root.wait_window(mode_dlg)
        self.mode = mode_dlg.result or "api"

        # 清除临时尺寸，根据模式重新设置
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.resizable(True, True)
        self.root.minsize(560, 480)
        self.root.configure(bg="#ffffff")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = self._load_config()
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.mod_folder_var = tk.StringVar(value=self.config.get("mod_folder", ""))
        self.engine_var = tk.StringVar(value=self.config.get("engine", "deepseek"))
        self.provider_var = tk.StringVar(value=self.config.get("provider", "DeepSeek"))
        self.api_url_var = tk.StringVar(value=self.config.get("api_url", ""))
        self.api_model_var = tk.StringVar(value=self.config.get("api_model", ""))
        self.models_url_var = tk.StringVar(value=self.config.get("models_url", ""))
        self.auto_complete_url_var = tk.BooleanVar(
            value=bool(self.config.get("api_url_auto_complete", True))
        )
        self._fetched_models = []  # 缓存已获取的模型列表
        self._model_request_id = 0
        self._active_provider = None
        self.ollama_model_var = tk.StringVar(value=self.config.get("ollama_model", ""))
        self.output_dir_var = tk.StringVar(value=self.config.get("output_dir", ""))
        self.use_wiki_var = tk.BooleanVar(value=self.config.get("use_wiki", False))
        self.polish_after_generate_var = tk.BooleanVar(
            value=self.config.get("polish_after_generate", False)
        )
        self.max_output_tokens_var = tk.StringVar(value=self.config.get("max_output_tokens", ""))
        self.generating = False
        self._generation_events = queue.Queue()
        self._update_checking = False
        self._update_checked = False
        self._update_request_id = 0
        self._pending_update_result = None
        self.selected_mods = []
        self._detected_mods = []

        self._build_ui()
        self.root.after(50, self._poll_generation_events)
        self.root.update_idletasks()
        self._center_window()
        self._refresh_text()
        if self.mode == "api":
            self.generate_btn.config(state=tk.DISABLED, bg="#cccccc")
        self.set_info(t("starting"), "info")
        threading.Thread(target=self._startup_check, daemon=True).start()

    def _startup_check(self):
        global ollama_available, ollama_models, ollama_best_model
        ok = _check_deps()
        try:
            import ollama_adapter as oa
            avail, models = oa.check_ollama_available()
            ollama_available = avail
            ollama_models = models
            if avail and models:
                ollama_best_model = oa.find_best_model(models)
        except Exception:
            ollama_available = False
            ollama_models = []
            ollama_best_model = None
        self.root.after(0, self._on_startup_checked, ok)

    def _on_startup_checked(self, ok):
        global ollama_available, ollama_best_model
        # 依赖加载完成后，标准化 provider 并刷新 Combobox
        if ok and normalize_provider:
            prov = normalize_provider(self.provider_var.get())
            self.provider_var.set(prov)
            if hasattr(self, 'provider_combo'):
                self.provider_combo['values'] = list(PROVIDER_PRESETS.keys())
                self._on_provider_change(preserve_model=True)
        if ollama_available and ollama_best_model:
            self.engine_var.set("ollama")
            self.ollama_model_var.set(ollama_best_model)
            self._update_engine_ui()
            self.set_info(f"本地Ollama就绪 — 模型: {ollama_best_model}", "success")
        elif ok:
            self.set_info(t("ready"), "info")
        else:
            self.set_info(t("deps_missing"), "error")
            self.root.after(100, lambda: messagebox.showwarning(t("dep_error_title"), AI_IMPORT_ERROR))
        if ok:
            self._restore_selected_mods()
        self._check_config_ready()

    def _restore_selected_mods(self):
        """启动时自动检查上次的 Mod 文件夹：扫描 MOD 文件并恢复已选 Mod。

        只要 config 里保存过有效的 Mod 文件夹，启动就会自动扫描其中的
        .jar/.zip 并显示数量，用户无需重新浏览选择文件夹；
        文件夹未变化时还会按文件名恢复上次勾选的 Mod。
        """
        current_folder = self.mod_folder_var.get().strip()
        if not current_folder or not os.path.isdir(current_folder):
            return
        saved = self.config.get("selected_mods") or []
        saved_folder = self.config.get("selected_mods_folder") or ""
        try:
            same_folder = os.path.normcase(os.path.abspath(saved_folder)) == os.path.normcase(
                os.path.abspath(current_folder)
            )
        except Exception:
            same_folder = False
        if not same_folder:
            saved = []  # 文件夹已变化：只扫描，不恢复旧选择

        def _scan():
            try:
                mods = scan_mod_folder(current_folder)
            except Exception:
                mods = []
            self.root.after(0, self._apply_restored_mods, mods, list(saved))

        threading.Thread(target=_scan, daemon=True).start()

    def _apply_restored_mods(self, mods, saved):
        saved_set = set(saved or [])
        self._detected_mods = mods
        self.selected_mods = [m for m in mods if m.get("filename") in saved_set]
        n = len(self.selected_mods)
        total = len(mods)
        if n:
            self.mod_status_label.config(
                text=f"检测到 {total} 个Mod  |  已选: {n}", fg="#4caf50"
            )
        elif total:
            # 没有可恢复的选择：自动扫描结果已就绪，提示用户直接勾选
            self.mod_status_label.config(
                text=f"检测到 {total} 个Mod  |  已选: 0", fg="#888888"
            )
        else:
            self.mod_status_label.config(text="检测到 0 个Mod  |  已选: 0", fg="#888888")
        if hasattr(self, 'save_prompt_api_btn'):
            self.save_prompt_api_btn.config(state=tk.NORMAL if n > 0 else tk.DISABLED)
        if hasattr(self, 'mod_info_btn'):
            self.mod_info_btn.config(state=tk.NORMAL if n > 0 else tk.DISABLED)
        self._check_config_ready()
        # 恢复/扫描提示放在最后，避免被 _check_config_ready 的默认提示覆盖
        if n:
            self.set_info(f"已恢复上次选择的 {n} 个Mod", "success")
        elif total:
            self.set_info(
                f"已自动扫描 {total} 个Mod，点击「选择 Mod」勾选即可，无需重新选择文件夹",
                "info",
            )
        else:
            self.set_info("文件夹中没有检测到 .jar/.zip Mod 文件", "warning")

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {}

    def _initial_window_size(self):
        """Prefer the user's saved size, otherwise fit the current screen."""
        saved = self.config.get("window_size")
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                saved_w, saved_h = int(saved[0]), int(saved[1])
                if saved_w >= 560 and saved_h >= 480:
                    return saved_w, saved_h
            except (TypeError, ValueError):
                pass
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        default_w, default_h = (780, 920) if self.mode == "api" else (680, 780)
        max_w = max(560, int(screen_w * 0.95))
        max_h = max(480, int(screen_h * 0.92))
        return min(default_w, max_w), min(default_h, max_h)

    def _save_config(self):
        self.config["api_key"] = self.api_key_var.get().strip()
        self.config["mod_folder"] = self.mod_folder_var.get().strip()
        self.config["engine"] = self.engine_var.get()
        self.config["provider"] = self.provider_var.get()
        self.config["api_url"] = self.api_url_var.get().strip()
        self.config["api_model"] = self.api_model_var.get().strip()
        self.config["models_url"] = self.models_url_var.get().strip()
        self.config["api_url_auto_complete"] = bool(self.auto_complete_url_var.get())
        self.config["ollama_model"] = self.ollama_model_var.get()
        self.config["density"] = self.density_var.get()
        self.config["max_output_tokens"] = self.max_output_tokens_var.get().strip()
        self.config["output_dir"] = self.output_dir_var.get().strip()
        self.config["polish_after_generate"] = bool(
            self.polish_after_generate_var.get()
        )
        self.config["window_size"] = [
            self.root.winfo_width(),
            self.root.winfo_height(),
        ]
        # 记住本次选择的 Mod（文件名列表），下次启动自动恢复
        self.config["selected_mods"] = [
            m.get("filename", "") for m in self.selected_mods
        ]
        self.config["selected_mods_folder"] = self.mod_folder_var.get().strip()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e: messagebox.showerror("Error", str(e)); return False

    def _check_config_ready(self):
        if not AI_AVAILABLE:
            if self.mode == "api":
                self.generate_btn.config(state=tk.DISABLED, bg="#cccccc")
            self.set_info(t("deps_missing"), "error"); return
        mf = self.mod_folder_var.get().strip()
        if not mf or not os.path.isdir(mf):
            if self.mode == "api":
                self.generate_btn.config(state=tk.DISABLED, bg="#cccccc")
            self.set_info(t("select_mod"), "warning"); return
        if not self.selected_mods:
            if self.mode == "api":
                self.generate_btn.config(state=tk.DISABLED, bg="#cccccc")
            if hasattr(self, 'save_prompt_api_btn'):
                self.save_prompt_api_btn.config(state=tk.DISABLED)
            if hasattr(self, 'mod_info_btn'):
                self.mod_info_btn.config(state=tk.DISABLED)
            self.set_info(t("ready"), "info"); return
        # Import 模式只需要 Mod 和文件夹，不需要检查 API
        if self.mode == "import":
            self.set_info("已选择 {} 个Mod — 可保存提示词或粘贴JSON".format(len(self.selected_mods)), "success")
            return
        # API 模式继续检查
        engine = self.engine_var.get()
        if engine == "ollama":
            global ollama_available
            if ollama_available:
                self.generate_btn.config(state=tk.NORMAL, bg="#4caf50", activebackground="#388e3c")
                self.set_info("Ollama就绪 — 点击生成", "success")
            else:
                self.generate_btn.config(state=tk.DISABLED, bg="#cccccc")
                self.set_info("Ollama未运行。请先启动Ollama，或切换到DeepSeek API。", "warning")
            return
        api = self.api_key_var.get().strip()
        if api:
            self.generate_btn.config(state=tk.NORMAL, bg="#4caf50", activebackground="#388e3c")
            self.set_info(t("config_ready"), "success")
        else:
            self.generate_btn.config(state=tk.DISABLED, bg="#cccccc")
            self.set_info(t("enter_api"), "warning")

    def _switch_engine(self, engine):
        self.engine_var.set(engine)
        self._update_engine_ui()
        self._check_config_ready()
        self._save_config()

    def _update_engine_ui(self):
        if self.mode != "api":
            return
        global ollama_available, ollama_best_model, ollama_models
        engine = self.engine_var.get()
        if engine == "ollama":
            self.engine_ds_btn.config(bg="#e0e0e0", fg="#555555")
            self.engine_ollama_btn.config(bg="#4caf50", fg="#ffffff")
            self.api_frame.pack_forget()
            self.provider_frame.pack_forget()
            if ollama_available and ollama_best_model:
                self.ollama_status_label.config(text=f"✓ 模型: {ollama_best_model}", fg="#4caf50")
            elif ollama_available:
                self.ollama_status_label.config(text="Ollama运行中，但未检测到推荐模型", fg="#ff9800")
            else:
                self.ollama_status_label.config(text="⚠ 未检测到Ollama", fg="#f44336")
        else:
            self.engine_ds_btn.config(bg="#4a90d9", fg="#ffffff")
            self.engine_ollama_btn.config(bg="#e0e0e0", fg="#555555")
            self.ollama_status_label.config(text="")
            self.api_frame.pack(before=self.engine_frame, fill=tk.X, pady=(0, 15))
            self.provider_frame.pack(before=self.api_frame, fill=tk.X, pady=(0, 6))
            self._on_provider_change(preserve_model=True, auto_fetch=False)

    def _on_provider_change(self, preserve_model=False, auto_fetch=True):
        """供应商切换时：更新URL字段状态、模型列表URL行、提示、清空已获取模型"""
        provider = self.provider_var.get()
        is_custom = (provider == "第三方自定义")
        preset = PROVIDER_PRESETS.get(provider, {})
        provider_changed = provider != self._active_provider
        if provider_changed:
            self._model_request_id += 1  # Ignore any response from the previous provider.

        # ── URL 字段 ──
        if is_custom:
            # 第三方自定义：清空URL让用户输入（如果当前是预设URL）
            cur_url = self.api_url_var.get().strip()
            if not cur_url or any(cur_url == p.get("chat_url", "") for p in PROVIDER_PRESETS.values()):
                self.api_url_var.set("")
            self.api_url_entry.config(state=tk.NORMAL, bg="#ffffff", fg="#333333")
            self.api_url_label.config(text="API URL:", fg="#555555")
            self.api_url_hint_label.config(text="可填完整地址或基础地址（未含 /chat/completions 时自动补全）", fg="#888888")
        else:
            # 预设服务商：自动填入URL并设为只读
            chat_url = preset.get("chat_url", "")
            self.api_url_var.set(chat_url)
            self.api_url_entry.config(state="readonly", readonlybackground="#f5f5f5", fg="#888888")
            self.api_url_label.config(text="API URL (预设):", fg="#888888")
            self.api_url_hint_label.config(text="", fg="#aaaaaa")

        # ── 模型列表URL行：仅第三方自定义时显示 ──
        if hasattr(self, 'models_url_row'):
            if is_custom:
                # 在 URL 行之后、模型行之前插入
                self.models_url_row.pack(fill=tk.X, pady=(0, 4), after=self.api_url_entry.master)
                self.models_url_entry.config(state=tk.NORMAL, bg="#ffffff", fg="#333333")
            else:
                self.models_url_row.pack_forget()
                # 预设服务商清空自定义 models_url（用预设的）
                self.models_url_var.set("")

        # ── API 完整地址开关行：仅第三方自定义时显示 ──
        if hasattr(self, 'auto_complete_row'):
            if is_custom:
                self.auto_complete_row.pack(
                    fill=tk.X, pady=(0, 4),
                    after=self.models_url_row if hasattr(self, 'models_url_row') else self.api_url_entry.master,
                )
            else:
                self.auto_complete_row.pack_forget()

        # ── 服务商特定提示 ──
        if hasattr(self, 'provider_hint_label'):
            hint = preset.get("hint", "")
            if hint:
                self.provider_hint_label.config(text=f"💡 {hint}")
                self.provider_hint_label.pack(fill=tk.X, pady=(0, 4), after=self.models_url_row if is_custom else self.api_url_entry.master)
            else:
                self.provider_hint_label.pack_forget()

        # ── 模型默认值 ──
        if not is_custom:
            default_model = preset.get("model", "")
            current_model = self.api_model_var.get().strip()
            if resolve_provider_model:
                migrated_model = resolve_provider_model(provider, current_model)
                if migrated_model != current_model:
                    self.api_model_var.set(migrated_model)
            if default_model and (not self.api_model_var.get().strip() or (provider_changed and not preserve_model)):
                self.api_model_var.set(default_model)
        elif provider_changed and not preserve_model:
            # 如果当前模型是某个预设的默认模型，清空
            cur_model = self.api_model_var.get().strip()
            if cur_model and any(cur_model == p.get("model", "") for p in PROVIDER_PRESETS.values()):
                self.api_model_var.set("")

        # ── 清空已获取的模型列表 ──
        self._fetched_models = []
        if hasattr(self, 'api_model_combo'):
            self.api_model_combo['values'] = []
        if hasattr(self, 'model_fetch_label'):
            self.model_fetch_label.config(text="可手动输入模型ID", fg="#aaaaaa")
        if hasattr(self, 'fetch_models_btn'):
            self.fetch_models_btn.config(state=tk.NORMAL)

        self._active_provider = provider
        self._save_config()

        # 如果已有API Key且非自定义，自动获取模型列表
        if auto_fetch and not is_custom and self.api_key_var.get().strip():
            self._on_fetch_models()

    def _on_fetch_models(self):
        """从服务商API获取可用模型列表；失败时提示用户可手动输入，不弹窗阻断"""
        if not fetch_provider_models:
            messagebox.showwarning("提示", "依赖未加载完成，请稍后再试。")
            return
        provider = self.provider_var.get()
        is_custom = (provider == "第三方自定义")
        api_key = self.api_key_var.get().strip()
        if not api_key:
            # 不弹窗，仅在标签提示，保持Combobox可手动输入
            self.model_fetch_label.config(text="请先填写 API Key，或直接手动输入模型ID", fg="#ff9800")
            return

        # 确定models_url
        if is_custom:
            # 第三方自定义：优先使用用户填写的 models_url，为空时从 chat_url 推导
            models_url = self.models_url_var.get().strip()
            if not models_url:
                chat_url = self.api_url_var.get().strip()
                if not chat_url:
                    self.model_fetch_label.config(text="请先填写 API URL，或直接手动输入模型ID", fg="#ff9800")
                    return
                if derive_models_url:
                    models_url = derive_models_url(chat_url)
                if not models_url:
                    # 推导失败：提示用户可手动填写 models_url 或直接输入模型ID
                    self.model_fetch_label.config(text="无法自动推导模型列表URL，请在上方填写或直接手动输入模型ID", fg="#ff9800")
                    return
        else:
            preset = PROVIDER_PRESETS.get(provider, {})
            models_url = preset.get("models_url", "")

        if not models_url:
            # 预设服务商无 models_url（如火山引擎）：提示手动输入
            self.model_fetch_label.config(text="该服务商不支持自动获取，请直接手动输入模型ID", fg="#ff9800")
            return

        self.model_fetch_label.config(text="正在获取模型列表...", fg="#ff9800")
        self.fetch_models_btn.config(state=tk.DISABLED)
        self._model_request_id += 1
        request_id = self._model_request_id
        request_provider = provider

        def _fetch_thread():
            models, err = fetch_provider_models(api_key, models_url)
            self.root.after(
                0,
                self._on_models_fetched,
                request_id,
                request_provider,
                models_url,
                models,
                err,
            )

        threading.Thread(target=_fetch_thread, daemon=True).start()

    def _on_models_fetched(self, request_id, provider, models_url, models, err):
        if request_id != self._model_request_id or provider != self.provider_var.get():
            return
        self.fetch_models_btn.config(state=tk.NORMAL)
        if provider == "第三方自定义":
            current_models_url = self.models_url_var.get().strip()
            if not current_models_url and derive_models_url:
                current_models_url = derive_models_url(self.api_url_var.get().strip())
        else:
            current_models_url = PROVIDER_PRESETS.get(provider, {}).get("models_url", "")
        if current_models_url != models_url:
            self.model_fetch_label.config(text="接口地址已变化，请重新获取模型列表", fg="#ff9800")
            return
        if err:
            self.model_fetch_label.config(text=f"❌ {err}", fg="#f44336")
            if models:
                self.api_model_combo['values'] = models
                self._fetched_models = models
            return
        if not models:
            self.model_fetch_label.config(text="⚠ 未获取到模型", fg="#ff9800")
            return
        self._fetched_models = models
        self.api_model_combo['values'] = models
        # Keep a valid choice; otherwise prefer the provider default over an arbitrary first ID.
        cur = self.api_model_var.get().strip()
        selected = select_provider_model(provider, cur, models) if select_provider_model else cur
        if not selected:
            selected = models[0]
        if selected != cur:
            self.api_model_var.set(selected)
        count = len(models)
        self.model_fetch_label.config(text=f"✓ 获取到 {count} 个模型，可直接输入模型ID", fg="#4caf50")

    def _build_ui(self):
        try:
            df = ("Microsoft YaHei", 10); tf = ("Microsoft YaHei", 26, "bold")
            sf = ("Microsoft YaHei", 9); bf = ("Microsoft YaHei", 11, "bold")
        except Exception:
            df = ("TkDefaultFont", 10); tf = ("TkDefaultFont", 26, "bold")
            sf = ("TkDefaultFont", 9); bf = ("TkDefaultFont", 11, "bold")

        # 窗口大小根据模式调整
        window_w, window_h = self._initial_window_size()
        self.root.geometry(f"{window_w}x{window_h}")

        shell = tk.Frame(self.root, bg="#ffffff")
        shell.pack(fill=tk.BOTH, expand=True)

        fixed_host = tk.Frame(shell, bg="#ffffff")
        fixed_host.pack(side=tk.BOTTOM, fill=tk.X)

        scroll_host = tk.Frame(shell, bg="#ffffff")
        scroll_host.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._main_canvas = tk.Canvas(
            scroll_host,
            bg="#ffffff",
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self._main_scrollbar = ttk.Scrollbar(
            scroll_host,
            orient=tk.VERTICAL,
            command=self._main_canvas.yview,
        )
        self._main_canvas.configure(yscrollcommand=self._main_scrollbar.set)
        self._main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        mf = tk.Frame(self._main_canvas, bg="#ffffff", padx=30, pady=20)
        self._main_content = mf
        self._main_canvas_window = self._main_canvas.create_window(
            (0, 0),
            window=mf,
            anchor=tk.NW,
        )
        mf.bind("<Configure>", self._update_main_scrollregion, add="+")
        self._main_canvas.bind("<Configure>", self._resize_main_content, add="+")
        self.root.bind_all("<MouseWheel>", self._on_main_mousewheel, add="+")

        # Title
        top = tk.Frame(mf, bg="#ffffff"); top.pack(fill=tk.X)
        tk.Label(top, text="AutoFTBQ", font=tf, fg="#1a1a1a", bg="#ffffff").pack(side=tk.LEFT)
        self.lang_btn = tk.Button(top, text="EN", font=sf, bg="#f0f0f0", fg="#555555", bd=1, relief=tk.SOLID, cursor="hand2", activebackground="#e0e0e0", padx=10, pady=2, command=self._toggle_lang)
        self.lang_btn.pack(side=tk.RIGHT)
        self.subtitle_label = tk.Label(mf, font=("Microsoft YaHei", 11), fg="#888888", bg="#ffffff")
        self.subtitle_label.pack(pady=(2, 20))
        ttk.Separator(mf, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 20))

        # ── Mod Folder（两种模式共用） ──
        sec2 = tk.Frame(mf, bg="#ffffff"); sec2.pack(fill=tk.X, pady=(0, 18))
        self.mod_label = tk.Label(sec2, font=("Microsoft YaHei", 12, "bold"), fg="#333333", bg="#ffffff")
        self.mod_label.pack(anchor=tk.W)
        self.mod_desc_label = tk.Label(sec2, font=sf, fg="#aaaaaa", bg="#ffffff")
        self.mod_desc_label.pack(anchor=tk.W, pady=(2, 6))
        row2 = tk.Frame(sec2, bg="#ffffff"); row2.pack(fill=tk.X)
        self.mod_entry = tk.Entry(row2, textvariable=self.mod_folder_var, font=df, bd=1, relief=tk.SOLID, fg="#333333", bg="#f5f5f5", state="readonly", readonlybackground="#f5f5f5")
        self.mod_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.browse_btn = tk.Button(row2, font=df, command=self._browse_mod_folder, bg="#f0f0f0", fg="#555555", bd=1, relief=tk.SOLID, cursor="hand2", activebackground="#e0e0e0", padx=16)
        self.browse_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.select_mods_btn = tk.Button(row2, font=sf, command=self._open_mod_select, bg="#e8f5e9", fg="#2e7d32", bd=1, relief=tk.SOLID, cursor="hand2", activebackground="#c8e6c9", padx=10)
        self.select_mods_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.mod_info_btn = tk.Button(row2, font=sf, command=self._open_mod_info, bg="#e3f2fd", fg="#1565c0", bd=1, relief=tk.SOLID, cursor="hand2", activebackground="#bbdefb", padx=10, state=tk.DISABLED)
        self.mod_info_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.mod_status_label = tk.Label(sec2, font=sf, fg="#888888", bg="#ffffff")
        self.mod_status_label.pack(anchor=tk.W, pady=(4, 0))

        # ── 输出目录（两种模式共用） ──
        sec3 = tk.Frame(mf, bg="#ffffff"); sec3.pack(fill=tk.X, pady=(0, 10))
        tk.Label(sec3, text="输出目录 (可选)", font=("Microsoft YaHei", 10, "bold"),
                 fg="#555555", bg="#ffffff").pack(anchor=tk.W)
        tk.Label(sec3, text="选择整合包后会自动识别其 FTB Quests 目录；也可以手动修改",
                 font=sf, fg="#aaaaaa", bg="#ffffff").pack(anchor=tk.W, pady=(2, 4))
        row3 = tk.Frame(sec3, bg="#ffffff"); row3.pack(fill=tk.X)
        self.output_entry = tk.Entry(row3, textvariable=self.output_dir_var, font=df,
                                      bd=1, relief=tk.SOLID, fg="#333333", bg="#f5f5f5",
                                      state="readonly", readonlybackground="#f5f5f5")
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.output_browse_btn = tk.Button(row3, text="📁", font=sf, command=self._browse_output_dir,
                                            bg="#f0f0f0", fg="#555555", bd=1, relief=tk.SOLID,
                                            cursor="hand2", activebackground="#e0e0e0", padx=10)
        self.output_browse_btn.pack(side=tk.RIGHT, padx=(6, 0))

        if self.mode == "api":
            self._build_api_specific(mf, df, sf, bf)
        else:
            self._build_import_specific(mf, df)

        self._build_fixed_action_area(fixed_host, sf, bf)

        self.footer_label = tk.Label(mf, font=("Microsoft YaHei", 8), fg="#cccccc", bg="#ffffff")
        self.footer_label.pack(pady=(15, 0))

        # 版本检测标签（点击可跳转下载）
        self.update_label = tk.Label(mf, font=("Microsoft YaHei", 8), fg="#888888", bg="#ffffff", cursor="hand2")
        self.update_label.pack(before=self.footer_label, pady=(0, 2))
        self.update_label.bind("<Button-1>", self._on_update_click)

    def _update_main_scrollregion(self, event=None):
        if hasattr(self, "_main_canvas"):
            self._main_canvas.configure(scrollregion=self._main_canvas.bbox("all"))

    def _resize_main_content(self, event):
        self._main_canvas.itemconfigure(self._main_canvas_window, width=event.width)
        self._update_main_scrollregion()

    def _on_main_mousewheel(self, event):
        """Scroll the main form without stealing wheel input from text/list widgets."""
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is None or isinstance(widget, (tk.Text, tk.Listbox)):
            return None

        current = widget
        inside_main_content = False
        while current is not None:
            if current in (self._main_content, self._main_canvas):
                inside_main_content = True
                break
            parent_name = current.winfo_parent()
            if not parent_name:
                current = None
                continue
            try:
                current = current._nametowidget(parent_name)
            except (KeyError, tk.TclError):
                current = None
        if not inside_main_content:
            return None

        bounds = self._main_canvas.bbox("all")
        if not bounds or bounds[3] <= self._main_canvas.winfo_height():
            return None
        steps = max(1, min(3, abs(int(event.delta)) // 120 or 1))
        self._main_canvas.yview_scroll(-steps if event.delta > 0 else steps, "units")
        return "break"

    def _build_fixed_action_area(self, parent, sf, bf):
        """Keep generation status and primary actions visible on small screens."""
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X)
        panel = tk.Frame(parent, bg="#ffffff", padx=30, pady=10)
        panel.pack(fill=tk.X)

        self.info_frame = tk.Frame(panel, bg="#f8f8f8", padx=12, pady=7)
        self.info_frame.pack(fill=tk.X, pady=(0, 7))
        self.info_label = tk.Label(
            self.info_frame,
            font=sf,
            fg="#888888",
            bg="#f8f8f8",
            wraplength=600,
            justify=tk.LEFT,
        )
        self.info_label.pack(anchor=tk.W)
        self.info_frame.bind(
            "<Configure>",
            lambda event: self.info_label.configure(wraplength=max(240, event.width - 24)),
            add="+",
        )

        progress_row = tk.Frame(panel, bg="#ffffff")
        progress_row.pack(fill=tk.X, pady=(0, 8))
        self.progress_label = tk.Label(
            progress_row,
            text="",
            font=sf,
            fg="#888888",
            bg="#ffffff",
            anchor=tk.W,
        )
        self.progress_label.pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(progress_row, mode="determinate", value=0)
        self.progress_bar.pack(fill=tk.X, pady=(3, 0))

        btnf = tk.Frame(panel, bg="#ffffff")
        btnf.pack(fill=tk.X)
        if self.mode == "api":
            self.save_btn = tk.Button(
                btnf,
                font=bf,
                command=self._on_save_config,
                bg="#4a90d9",
                fg="#ffffff",
                bd=0,
                relief=tk.FLAT,
                cursor="hand2",
                activebackground="#357abd",
                activeforeground="#ffffff",
                padx=20,
                pady=8,
            )
            self.save_btn.pack(side=tk.LEFT, padx=(0, 10))
            self.generate_btn = tk.Button(
                btnf,
                font=bf,
                command=self._on_generate,
                bg="#cccccc",
                fg="#ffffff",
                bd=0,
                relief=tk.FLAT,
                cursor="hand2",
                activebackground="#cccccc",
                activeforeground="#ffffff",
                padx=20,
                pady=8,
                state=tk.DISABLED,
            )
            self.generate_btn.pack(side=tk.RIGHT)
        else:
            self.save_prompt_api_btn = tk.Button(
                btnf,
                text="📤 保存提示词文件",
                font=("Microsoft YaHei", 10),
                command=self._on_save_prompt,
                bg="#2196f3",
                fg="#ffffff",
                bd=0,
                relief=tk.FLAT,
                cursor="hand2",
                activebackground="#1976d2",
                activeforeground="#ffffff",
                padx=14,
                pady=8,
                state=tk.DISABLED,
            )
            self.save_prompt_api_btn.pack(side=tk.LEFT)
            self.import_btn = tk.Button(
                btnf,
                text="📄 粘贴并生成 SNBT",
                font=("Microsoft YaHei", 11, "bold"),
                command=self._on_import_json,
                bg="#4caf50",
                fg="#ffffff",
                bd=0,
                relief=tk.FLAT,
                cursor="hand2",
                activebackground="#388e3c",
                activeforeground="#ffffff",
                padx=20,
                pady=8,
            )
            self.import_btn.pack(side=tk.RIGHT)

    def _build_api_specific(self, mf, df, sf, bf):
        """构建 API 模式专属 UI"""
        # ── API Key ──
        self.api_frame = tk.Frame(mf, bg="#ffffff")
        self.api_frame.pack(fill=tk.X, pady=(0, 18))
        self.api_label = tk.Label(self.api_frame, font=("Microsoft YaHei", 12, "bold"), fg="#333333", bg="#ffffff")
        self.api_label.pack(anchor=tk.W)
        self.api_desc_label = tk.Label(self.api_frame, font=sf, fg="#aaaaaa", bg="#ffffff")
        self.api_desc_label.pack(anchor=tk.W, pady=(2, 6))
        row = tk.Frame(self.api_frame, bg="#ffffff"); row.pack(fill=tk.X)
        self.api_entry = tk.Entry(row, textvariable=self.api_key_var, font=df, show="*", bd=1, relief=tk.SOLID, fg="#333333", bg="#f5f5f5")
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.api_entry.bind("<KeyRelease>", lambda e: self._check_config_ready())
        self.api_entry.bind("<Return>", lambda e: self._on_fetch_models() if self.provider_var.get() != "第三方自定义" else None)
        self.show_btn = tk.Button(row, font=sf, width=5, command=self._toggle_key_vis, bg="#f0f0f0", fg="#555555", bd=1, relief=tk.SOLID, cursor="hand2", activebackground="#e0e0e0")
        self.show_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self._key_visible = False

        # ── Engine Selector ──
        self.engine_frame = tk.Frame(mf, bg="#ffffff")
        self.engine_frame.pack(fill=tk.X, pady=(0, 12))
        self.engine_label = tk.Label(self.engine_frame, text="AI引擎:", font=("Microsoft YaHei", 10, "bold"), fg="#555555", bg="#ffffff")
        self.engine_label.pack(side=tk.LEFT, padx=(0, 10))
        self.engine_ds_btn = tk.Button(self.engine_frame, text="API", font=("Microsoft YaHei", 10),
                                        command=lambda: self._switch_engine("deepseek"),
                                        bg="#4a90d9", fg="#ffffff", bd=1, relief=tk.SOLID,
                                        cursor="hand2", padx=14, pady=3)
        self.engine_ds_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.engine_ollama_btn = tk.Button(self.engine_frame, text="Ollama 本地", font=("Microsoft YaHei", 10),
                                            command=lambda: self._switch_engine("ollama"),
                                            bg="#e0e0e0", fg="#555555", bd=1, relief=tk.SOLID,
                                            cursor="hand2", padx=14, pady=3)
        self.engine_ollama_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.ollama_status_label = tk.Label(self.engine_frame, text="", font=("Microsoft YaHei", 9), fg="#888888", bg="#ffffff")
        self.ollama_status_label.pack(side=tk.LEFT, padx=(12, 0))

        # ── API 服务商选择（仅 API 模式） ──
        self.provider_frame = tk.Frame(mf, bg="#ffffff")
        self.provider_frame.pack(fill=tk.X, pady=(0, 8))

        # Row 1: 服务商
        prov_row1 = tk.Frame(self.provider_frame, bg="#ffffff")
        prov_row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(prov_row1, text="服务商:", font=("Microsoft YaHei", 9, "bold"),
                 fg="#555555", bg="#ffffff").pack(side=tk.LEFT, padx=(0, 8))
        self.provider_combo = ttk.Combobox(prov_row1, textvariable=self.provider_var,
                                            values=list(PROVIDER_PRESETS.keys()),
                                            state="readonly", width=20, font=("Microsoft YaHei", 9))
        self.provider_combo.pack(side=tk.LEFT)
        self.provider_combo.bind("<<ComboboxSelected>>", lambda e: self._on_provider_change())

        # Row 2: API URL（仅第三方自定义时可编辑）
        prov_row2 = tk.Frame(self.provider_frame, bg="#ffffff")
        prov_row2.pack(fill=tk.X, pady=(0, 4))
        self.api_url_label = tk.Label(prov_row2, text="API URL:", font=("Microsoft YaHei", 9),
                                       fg="#888888", bg="#ffffff")
        self.api_url_label.pack(side=tk.LEFT, padx=(0, 4))
        self.api_url_entry = tk.Entry(prov_row2, textvariable=self.api_url_var,
                                       font=("Microsoft YaHei", 9), bd=1, relief=tk.SOLID,
                                       fg="#555555", bg="#fafafa")
        self.api_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.api_url_hint_label = tk.Label(prov_row2, text="", font=("Microsoft YaHei", 8),
                                            fg="#aaaaaa", bg="#ffffff")
        self.api_url_hint_label.pack(side=tk.LEFT, padx=(6, 0))

        # Row 2b: 模型列表URL（仅第三方自定义时显示，可选）
        self.models_url_row = tk.Frame(self.provider_frame, bg="#ffffff")
        # 默认不 pack，_on_provider_change 会控制显示
        tk.Label(self.models_url_row, text="模型列表URL (可选):", font=("Microsoft YaHei", 8),
                 fg="#888888", bg="#ffffff").pack(side=tk.LEFT, padx=(0, 4))
        self.models_url_entry = tk.Entry(self.models_url_row, textvariable=self.models_url_var,
                                          font=("Microsoft YaHei", 8), bd=1, relief=tk.SOLID,
                                          fg="#555555", bg="#fafafa")
        self.models_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(self.models_url_row, text="留空自动推导", font=("Microsoft YaHei", 7),
                 fg="#aaaaaa", bg="#ffffff").pack(side=tk.LEFT, padx=(4, 0))

        # Row 2c: API 完整地址开关（仅第三方自定义时显示）
        self.auto_complete_row = tk.Frame(self.provider_frame, bg="#ffffff")
        self.auto_complete_check = tk.Checkbutton(
            self.auto_complete_row,
            text="自动补全 /chat/completions（基础地址自动补全，如 .../api/coding/v3 → .../v3/chat/completions）",
            variable=self.auto_complete_url_var,
            font=("Microsoft YaHei", 8),
            fg="#666666", bg="#ffffff", activebackground="#ffffff",
            selectcolor="#ffffff", command=self._save_config,
        )
        self.auto_complete_check.pack(side=tk.LEFT, anchor=tk.W)
        # 默认不 pack，_on_provider_change 会控制显示

        # Row 2d: 服务商特定提示（如火山引擎的 Endpoint ID 提示）
        self.provider_hint_label = tk.Label(self.provider_frame, text="", font=("Microsoft YaHei", 8),
                                             fg="#e65100", bg="#fff8e1", wraplength=680, justify=tk.LEFT,
                                             anchor=tk.W)
        # 默认不显示，_on_provider_change 控制

        # Row 3: 模型选择（下拉 + 手动输入 + 刷新按钮）
        prov_row3 = tk.Frame(self.provider_frame, bg="#ffffff")
        prov_row3.pack(fill=tk.X, pady=(0, 2))
        tk.Label(prov_row3, text="模型:", font=("Microsoft YaHei", 9),
                 fg="#888888", bg="#ffffff").pack(side=tk.LEFT, padx=(0, 4))
        self.api_model_combo = ttk.Combobox(prov_row3, textvariable=self.api_model_var,
                                            values=[], state="normal", width=28,
                                            font=("Microsoft YaHei", 9))
        self.api_model_combo.pack(side=tk.LEFT)
        self.fetch_models_btn = tk.Button(prov_row3, text="🔄 获取模型", font=("Microsoft YaHei", 8),
                                           command=self._on_fetch_models, bg="#e8f5e9", fg="#2e7d32",
                                           bd=1, relief=tk.SOLID, cursor="hand2", padx=8, pady=2)
        self.fetch_models_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.model_fetch_label = tk.Label(prov_row3, text="可手动输入模型ID", font=("Microsoft YaHei", 8),
                                           fg="#aaaaaa", bg="#ffffff")
        self.model_fetch_label.pack(side=tk.LEFT, padx=(8, 0))

        # ── Wiki 增强复选框 ──
        wiki_row = tk.Frame(mf, bg="#ffffff")
        wiki_row.pack(fill=tk.X, pady=(0, 6))
        # ── 任务密度选择 ──
        density_row = tk.Frame(mf, bg="#ffffff")
        density_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(density_row, text="任务密度:", font=("Microsoft YaHei", 9, "bold"), fg="#555555", bg="#ffffff").pack(side=tk.LEFT, padx=(0, 8))
        self.density_var = tk.StringVar(value=self.config.get("density", "medium"))
        for val, label in [("light", "精简"), ("medium", "适中"), ("rich", "丰富"), ("max", "拉满")]:
            tk.Radiobutton(density_row, text=label, variable=self.density_var, value=val,
                           font=("Microsoft YaHei", 9), fg="#555555", bg="#ffffff",
                           activebackground="#ffffff", selectcolor="#ffffff",
                           command=self._save_config).pack(side=tk.LEFT, padx=(0, 8))

        # ── 最大 Token 数 ──
        token_row = tk.Frame(mf, bg="#ffffff")
        token_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(token_row, text="最大Token数:", font=("Microsoft YaHei", 9, "bold"), fg="#555555", bg="#ffffff").pack(side=tk.LEFT, padx=(0, 8))
        self.max_output_tokens_entry = tk.Entry(token_row, textvariable=self.max_output_tokens_var,
                                                  font=("Microsoft YaHei", 9), bd=1, relief=tk.SOLID,
                                                  fg="#555555", bg="#fafafa", width=12)
        self.max_output_tokens_entry.pack(side=tk.LEFT)
        tk.Label(token_row, text="(留空自动，例如32768)", font=("Microsoft YaHei", 8), fg="#aaaaaa", bg="#ffffff").pack(side=tk.LEFT, padx=(8, 0))

        self.use_wiki_check = tk.Checkbutton(wiki_row, text="使用 MC百科 Wiki 数据增强（需要网络）",
                                              variable=self.use_wiki_var, font=("Microsoft YaHei", 9),
                                              fg="#666666", bg="#ffffff", activebackground="#ffffff",
                                              selectcolor="#ffffff", command=self._save_config)
        self.use_wiki_check.pack(side=tk.LEFT)

        polish_row = tk.Frame(mf, bg="#ffffff")
        polish_row.pack(fill=tk.X, pady=(0, 8))
        self.polish_after_generate_check = tk.Checkbutton(
            polish_row,
            text="AI 文案润色",
            variable=self.polish_after_generate_var,
            font=("Microsoft YaHei", 9),
            fg="#666666",
            bg="#ffffff",
            activebackground="#ffffff",
            selectcolor="#ffffff",
            command=self._save_config,
        )
        self.polish_after_generate_check.pack(side=tk.LEFT)
        tk.Label(
            polish_row,
            text="功能鸡肋，token充足时可以试试=D",
            font=("Microsoft YaHei", 8),
            fg="#aaaaaa",
            bg="#ffffff",
        ).pack(side=tk.LEFT, padx=(6, 0))

    def _build_import_specific(self, mf, df):
        """构建导入模式专属 UI"""
        tip_frame = tk.Frame(mf, bg="#f0faf0", padx=15, pady=12)
        tip_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(
            tip_frame,
            font=("Microsoft YaHei", 9),
            fg="#4caf50",
            bg="#f0faf0",
            wraplength=580,
            justify=tk.LEFT,
            text="💡 提示：先选 Mod → 点「保存提示词」→ 上传文件到网页AI → 粘贴返回的JSON → 点「生成SNBT」",
        ).pack(anchor=tk.W)

        # JSON 输入区（增大）
        json_label = tk.Label(mf, text="粘贴 AI 返回的 JSON：",
                               font=("Microsoft YaHei", 12, "bold"), fg="#333333", bg="#ffffff")
        json_label.pack(anchor=tk.W, pady=(0, 4))
        self.json_text = tk.Text(mf, height=8, font=("Consolas", 10),
                                  bg="#fafafa", fg="#333333", bd=1, relief=tk.SOLID,
                                  wrap=tk.WORD)
        self.json_text.pack(fill=tk.X)

    def _browse_output_dir(self):
        folder = filedialog.askdirectory(title="选择输出目录")
        if folder:
            self.output_dir_var.set(folder)
            self._save_config()

    def _browse_mod_folder(self):
        if scan_mod_folder is None:
            messagebox.showwarning("Warning", "请在依赖检查完成后再操作。")
            return
        folder = filedialog.askdirectory(title=t("mod_folder"))
        if folder:
            previous_folder = self.mod_folder_var.get().strip()
            previous_auto_output = suggested_output_dir(previous_folder) if previous_folder else ""
            current_output = self.output_dir_var.get().strip()
            self.mod_folder_var.set(folder)
            self.selected_mods = []
            if hasattr(self, 'save_prompt_api_btn'):
                self.save_prompt_api_btn.config(state=tk.DISABLED)
            if hasattr(self, 'mod_info_btn'):
                self.mod_info_btn.config(state=tk.DISABLED)
            try:
                self._detected_mods = scan_mod_folder(folder)
                n = len(self._detected_mods)
                info = resolve_instance(folder)
                version_text = ""
                if info and (info.minecraft_version or info.loader):
                    version_text = f"  |  {info.minecraft_version or '未知版本'} {info.loader}".rstrip()
                self.mod_status_label.config(text=f"检测到 {n} 个Mod  |  已选: 0{version_text}", fg="#888888")
                output_was_automatic = (
                    previous_auto_output
                    and os.path.normcase(os.path.abspath(current_output))
                    == os.path.normcase(os.path.abspath(previous_auto_output))
                )
                if not current_output or output_was_automatic:
                    detected_output = suggested_output_dir(folder)
                    if detected_output:
                        self.output_dir_var.set(detected_output)
                if n:
                    self.set_info(t("found_mods", n), "success")
                else:
                    self.set_info(t("no_mods"), "warning")
            except Exception as e:
                self.set_info(f"{t('dir_error')}: {e}", "error")
            # 立即记住新文件夹，下次启动自动扫描恢复
            self._save_config()
            self._check_config_ready()

    def _open_mod_select(self):
        if scan_mod_folder is None:
            messagebox.showwarning("Warning", "依赖未就绪，请稍等。")
            return
        if not self._detected_mods:
            messagebox.showinfo("Info", "请先选择Mod文件夹。")
            return
        selected_filenames = {
            mod.get("filename") for mod in self.selected_mods
        }
        dlg = ModSelectDialog(
            self.root,
            self._detected_mods,
            selected_filenames=selected_filenames,
        )
        self.root.wait_window(dlg)
        if dlg.result is not None and dlg.result:
            self.selected_mods = []
            for m in self._detected_mods:
                if m["filename"] in dlg.result:
                    self.selected_mods.append(m)
            n = len(self.selected_mods)
            self.mod_status_label.config(text=f"检测到 {len(self._detected_mods)} 个Mod  |  已选: {n}", fg="#4caf50" if n else "#888888")
            if n > 0 and hasattr(self, 'save_prompt_api_btn'):
                self.save_prompt_api_btn.config(state=tk.NORMAL)
            if hasattr(self, 'mod_info_btn'):
                self.mod_info_btn.config(state=tk.NORMAL if n > 0 else tk.DISABLED)
            self._save_config()
        self._check_config_ready()

    def _open_mod_info(self):
        """打开 MOD 信息窗口（MC百科 / Modrinth 等平台查询详情）。"""
        if not self.selected_mods:
            messagebox.showinfo("提示", "请先选择 Mod，再查看 MOD 信息。")
            return
        try:
            import mod_info
            mod_info  # 确保模块可用
        except Exception as exc:
            messagebox.showerror("错误", f"无法加载 MOD 信息模块: {exc}")
            return
        ModInfoDialog(self.root, self.selected_mods)

    def _refresh_text(self):
        if self.mode == "api":
            self.subtitle_label.config(text=t("subtitle_api"))
        else:
            self.subtitle_label.config(text=t("subtitle_import"))
        if hasattr(self, 'api_label'):
            self.api_label.config(text=t("api_key"))
            self.api_desc_label.config(text=t("api_desc"))
        self.mod_label.config(text=t("mod_folder"))
        self.mod_desc_label.config(text=t("mod_desc"))
        self.browse_btn.config(text=t("browse"))
        self.select_mods_btn.config(text=t("select_mods"))
        if hasattr(self, 'save_btn'):
            self.save_btn.config(text=t("save_config"))
        self.lang_btn.config(text=t("lang"))
        if hasattr(self, 'show_btn') and hasattr(self, '_key_visible'):
            self.show_btn.config(text=t("hide") if self._key_visible else t("show"))
        if hasattr(self, 'generate_btn'):
            self.generate_btn.config(text=t("generating") if self.generating else t("generate"))
        self.footer_label.config(text=f"v{VERSION}  |  {t('author_line')}  |  {t('powered')}")
        self._start_update_check()
        self._check_config_ready()

    def _toggle_lang(self):
        global LANG
        LANG = "en" if LANG == "zh" else "zh"
        self._refresh_text()

    def _toggle_key_vis(self):
        if not hasattr(self, '_key_visible'):
            return
        self._key_visible = not self._key_visible
        if hasattr(self, 'api_entry'):
            self.api_entry.config(show="" if self._key_visible else "*")
        if hasattr(self, 'show_btn'):
            self.show_btn.config(text=t("hide") if self._key_visible else t("show"))

    def set_info(self, text, level="info"):
        if hasattr(self, 'info_label') and hasattr(self, 'info_frame'):
            self.info_label.config(text=text)
            c = {"success":("#4caf50","#f0faf0"),"warning":("#ff9800","#fffaf0"),"error":("#f44336","#fff5f5")}
            fg,bg = c.get(level,("#888888","#f8f8f8"))
            self.info_label.config(fg=fg, bg=bg); self.info_frame.config(bg=bg)

    def _on_progress(self, msg, pct):
        if self.generating:
            self._generation_events.put(("progress", msg, pct))

    def _poll_generation_events(self):
        try:
            while True:
                event, value, extra = self._generation_events.get_nowait()
                if event == "progress":
                    if self.generating:
                        self._set_progress_ui(value, extra)
                    continue
                try:
                    if event == "done":
                        self._on_done(value)
                    else:
                        self._on_fail(value)
                finally:
                    self.generating = False
                    self._on_finish()
        except queue.Empty:
            pass
        try:
            self.root.after(50, self._poll_generation_events)
        except tk.TclError:
            pass

    def _set_progress_ui(self, msg, pct):
        try:
            if hasattr(self, 'progress_label'):
                self.progress_label.config(text=msg)
            if hasattr(self, 'progress_bar'):
                self.progress_bar["value"] = pct
            self.set_info(msg, "info")
        except Exception: pass

    def _lock_ui(self, locked):
        s = tk.DISABLED if locked else tk.NORMAL
        try:
            if hasattr(self, 'api_entry'):
                self.api_entry.config(state=s)
            if hasattr(self, 'show_btn'):
                self.show_btn.config(state=s)
            self.mod_entry.config(state="readonly" if not locked else tk.DISABLED)
            self.browse_btn.config(state=s)
            if hasattr(self, 'output_entry'):
                self.output_entry.config(state="readonly" if not locked else tk.DISABLED)
            if hasattr(self, 'output_browse_btn'):
                self.output_browse_btn.config(state=s)
            if hasattr(self, 'save_btn'):
                self.save_btn.config(state=s)
            self.lang_btn.config(state=s)
            self.select_mods_btn.config(state=s)
            if hasattr(self, 'mod_info_btn'):
                # 生成中禁用；解锁时按是否有已选 Mod 恢复
                if locked:
                    self.mod_info_btn.config(state=tk.DISABLED)
                else:
                    self.mod_info_btn.config(
                        state=tk.NORMAL if self.selected_mods else tk.DISABLED
                    )
            if hasattr(self, 'save_prompt_api_btn'):
                self.save_prompt_api_btn.config(state=s)
            # 锁定供应商/模型相关控件
            if hasattr(self, 'provider_combo'):
                self.provider_combo.config(state="readonly" if not locked else tk.DISABLED)
            if hasattr(self, 'api_model_combo'):
                # 保持可编辑（normal），让用户随时手动输入模型ID
                self.api_model_combo.config(state="normal" if not locked else tk.DISABLED)
            if hasattr(self, 'fetch_models_btn'):
                self.fetch_models_btn.config(state=s)
            if hasattr(self, 'use_wiki_check'):
                self.use_wiki_check.config(state=s)
            if hasattr(self, 'polish_after_generate_check'):
                self.polish_after_generate_check.config(state=s)
            if hasattr(self, 'auto_complete_check'):
                self.auto_complete_check.config(state=s)
            # URL 字段：解锁时恢复到供应商对应的状态
            if hasattr(self, 'api_url_entry'):
                if locked:
                    self.api_url_entry.config(state=tk.DISABLED)
                else:
                    provider = self.provider_var.get()
                    if provider == "第三方自定义":
                        self.api_url_entry.config(state=tk.NORMAL)
                    else:
                        self.api_url_entry.config(state="readonly", readonlybackground="#f5f5f5")
            # 模型列表URL字段（仅第三方自定义可见时才需处理）
            if hasattr(self, 'models_url_entry'):
                if locked:
                    self.models_url_entry.config(state=tk.DISABLED)
                else:
                    provider = self.provider_var.get()
                    if provider == "第三方自定义":
                        self.models_url_entry.config(state=tk.NORMAL, bg="#fafafa", fg="#555555")
                    else:
                        self.models_url_entry.config(state=tk.DISABLED)
        except Exception: pass
        if locked:
            if hasattr(self, 'generate_btn'):
                self.generate_btn.config(text=t("generating"), state=tk.DISABLED, bg="#ff9800", activebackground="#ff9800")
            if hasattr(self, 'import_btn'):
                self.import_btn.config(text=t("generating"), state=tk.DISABLED, bg="#ff9800", activebackground="#ff9800")
        else:
            self._check_config_ready()
            if hasattr(self, 'generate_btn'):
                self.generate_btn.config(text=t("generate"))
            if hasattr(self, 'import_btn'):
                self.import_btn.config(text="📄 粘贴并生成 SNBT")
            if hasattr(self, 'progress_label'):
                self.progress_label.config(text="")
            if hasattr(self, 'progress_bar'):
                self.progress_bar["value"] = 0

    def _offer_save_prompt(self):
        """选完Mod后自动询问是否保存提示词文件（仅API模式）"""
        if not self.selected_mods:
            return
        want = messagebox.askyesno(
            "💡 保存提示词",
            f"已选择 {len(self.selected_mods)} 个Mod。\n\n"
            "是否保存「提示词+物品ID」文件？\n"
            "保存后可将文件上传至网页AI（如DeepSeek Chat），\n"
            "让AI根据完整物品列表生成更准确的任务书JSON。\n\n"
            "点击「是」立即保存，点击「否」跳过。"
        )
        if want:
            self._on_save_prompt()

    def _on_save_prompt(self):
        """保存提示词+物品ID文件（两种模式共用）"""
        if not self.selected_mods:
            messagebox.showwarning("提示", "请先选择Mod。")
            return
        try:
            mf = self.mod_folder_var.get().strip()
            self.set_info("正在扫描物品ID并生成提示词...", "info")
            prompt = build_full_prompt(self.selected_mods, mf, LANG)
            file_path = filedialog.asksaveasfilename(
                title="保存提示词文件",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile="FTBQ_prompt.txt"
            )
            if not file_path:
                return
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(prompt)
            file_size_kb = os.path.getsize(file_path) / 1024
            self.set_info(f"提示词已保存: {os.path.basename(file_path)} ({file_size_kb:.1f}KB)", "success")
            if self.mode == "import":
                msg = (
                    f"提示词文件已保存！\n\n"
                    f"📍 文件: {os.path.basename(file_path)}\n"
                    f"📦 大小: {file_size_kb:.1f} KB\n\n"
                    f"📤 下一步:\n"
                    f"1. 打开 chat.deepseek.com\n"
                    f"2. 上传这个文件（点击输入框旁的📎附件图标）\n"
                    f"3. 发送消息: 「请根据文件中的信息设计任务书JSON」\n"
                    f"4. AI返回JSON后，复制粘贴回本软件的输入框"
                )
            else:
                msg = (
                    f"提示词文件已保存！\n\n"
                    f"📍 文件: {os.path.basename(file_path)}\n"
                    f"📦 大小: {file_size_kb:.1f} KB\n\n"
                    f"📤 下一步:\n"
                    f"1. 打开 chat.deepseek.com\n"
                    f"2. 上传这个文件（点击输入框旁的📎附件图标）\n"
                    f"3. 发送消息: 「请根据文件中的信息设计任务书JSON」\n"
                    f"4. AI返回JSON后，可切换到导入模式粘贴"
                )
            messagebox.showinfo("✅ 保存成功", msg)
        except Exception as e:
            messagebox.showerror("错误", f"保存提示词失败: {e}")

    def _on_import_json(self):
        json_input = self.json_text.get("1.0", tk.END).strip()
        if not json_input:
            messagebox.showwarning("提示", "请先粘贴AI返回的JSON内容。")
            return
        self.generating = True
        self._lock_ui(True)
        self.set_info("正在转换SNBT...", "info")
        mf = self.mod_folder_var.get().strip()
        output_dir = self.output_dir_var.get().strip() or None
        threading.Thread(target=self._import_thread, args=(json_input, mf, output_dir), daemon=True).start()

    def _import_thread(self, json_input, mf, output_dir):
        try:
            out = import_json_to_snbt(
                json_text=json_input,
                selected_mods=self.selected_mods or None,
                mod_folder=mf if os.path.isdir(mf) else None,
                progress_callback=self._on_progress, output_dir=output_dir
            )
            self.root.after(0, self._on_done, out)
        except Exception as e:
            self.root.after(0, self._on_fail, str(e))
        finally:
            self.generating = False
            self.root.after(0, self._on_finish)

    def _on_save_config(self):
        engine = self.engine_var.get()
        if engine == "deepseek" and not self.api_key_var.get().strip():
            messagebox.showwarning("Warning", t("enter_api")); return
        if self._save_config(): self.set_info(t("saved_info"),"success"); self._check_config_ready(); messagebox.showinfo("Success", t("saved"))

    def _on_generate(self):
        if not AI_AVAILABLE: messagebox.showerror(t("dep_error_title"), AI_IMPORT_ERROR); return
        engine = self.engine_var.get()
        api_key = self.api_key_var.get().strip()
        if engine in ("deepseek", "generic") and not api_key:
            messagebox.showwarning("Warning", t("enter_api")); return
        if engine == "ollama" and not ollama_available:
            messagebox.showwarning("Warning", "Ollama未运行。请先启动Ollama。"); return
        if not self.selected_mods: messagebox.showwarning("Warning", "请点击「选择 Mod」勾选要生成的Mod"); return
        if not messagebox.askokcancel(t("confirm_title"), t("confirm_msg", len(self.selected_mods))): return
        self._save_config(); self.generating = True; self._lock_ui(True)
        self.set_info(t("preparing"), "info")
        mf = self.mod_folder_var.get().strip()
        # API 模式统一使用 generic 引擎（通过 GenericOpenAIClient 支持所有 OpenAI 兼容服务商）
        actual_engine = "generic" if engine == "deepseek" else engine
        # 第三方自定义时需要传入 api_url；预设服务商时 ai_module 会自动用 preset 的 chat_url
        provider = self.provider_var.get()
        api_url_val = self.api_url_var.get().strip()
        if provider != "第三方自定义":
            api_url_val = ""  # 让 ai_module 用 preset 的 URL
        threading.Thread(target=self._generate_thread, kwargs={
            "api_key": api_key if engine != "ollama" else None,
            "selected_mods": list(self.selected_mods),
            "lang": LANG,
            "engine": actual_engine,
            "ollama_model": self.ollama_model_var.get().strip(),
            "output_dir": self.output_dir_var.get().strip() or None,
            "use_wiki": bool(self.use_wiki_var.get()),
            "provider": provider,
            "api_url": api_url_val,
            "api_model": self.api_model_var.get().strip(),
            "density": self.density_var.get(),
            "max_output_tokens": int(self.max_output_tokens_var.get().strip()) if self.max_output_tokens_var.get().strip() else None,
            "polish_after_generate": bool(self.polish_after_generate_var.get()),
            "auto_complete": bool(self.auto_complete_url_var.get()),
        }, daemon=True).start()

    def _generate_thread(self, api_key, selected_mods, lang, engine, ollama_model, output_dir, use_wiki=False,
                         provider=None, api_url=None, api_model=None, density="medium",
                         max_output_tokens=None, polish_after_generate=False, auto_complete=True):
        try:
            mf = self.mod_folder_var.get().strip()
            out = generate_quest_book(
                api_key=api_key, selected_mods=selected_mods,
                mod_folder=mf, progress_callback=self._on_progress,
                lang=lang, engine=engine, ollama_model=ollama_model, output_dir=output_dir,
                use_wiki=use_wiki, provider=provider, api_url=api_url, api_model=api_model,
                density=density,
                max_output_tokens=max_output_tokens,
                polish_after_generate=polish_after_generate,
                auto_complete=auto_complete,
            )
            self._generation_events.put(("done", out, None))
        except Exception as e:
            log_path = os.path.join(APP_DIR, "generation_error.log")
            try:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {e}\n")
                    handle.write(traceback.format_exc())
            except OSError:
                log_path = ""
            detail = str(e) or type(e).__name__
            if log_path:
                detail += f"\n\n错误日志：{log_path}"
            self._generation_events.put(("failed", detail, None))

    def _on_done(self, path):
        self.set_info("Done!", "success")
        if hasattr(self, 'progress_bar'):
            self.progress_bar["value"] = 100
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text="Done!")
        # 生成中断（如 Token/额度不足）时保存的部分任务书：以警告形式提示
        partial_path = os.path.join(path, "partial_report.txt")
        if os.path.isfile(partial_path):
            self.set_info("部分生成完成 - 已完成章节已保存", "warning")
            detail = ""
            try:
                with open(partial_path, "r", encoding="utf-8") as handle:
                    detail = handle.read().strip()
            except OSError:
                pass
            if messagebox.askyesno(
                "部分生成完成",
                f"生成过程中断（可能是 Token 不足或额度用尽）。\n\n"
                f"已完成的部分任务书已保存到:\n{path}\n\n"
                f"{detail}\n\n打开目录查看？",
            ):
                try: os.startfile(path)
                except Exception: subprocess.Popen(["explorer", path], shell=True)
            return
        summary = ""
        try:
            quality_path = os.path.join(path, "quality_report.txt")
            with open(quality_path, "r", encoding="utf-8") as handle:
                values = {}
                for line in handle:
                    if ": " in line:
                        key, value = line.strip().split(": ", 1)
                        if key in ("状态", "章节", "任务"):
                            values[key] = value
                if values:
                    summary = (
                        f"\n\n质量检查: {values.get('状态', '已完成')}"
                        f"  |  {values.get('章节', '?')} 章节"
                        f"  |  {values.get('任务', '?')} 任务"
                    )
        except (OSError, ValueError):
            summary = ""
        if messagebox.askyesno(t("success_title"), t("success_msg", path) + summary):
            try: os.startfile(path)
            except Exception: subprocess.Popen(["explorer", path], shell=True)

    def _on_fail(self, msg):
        self.set_info(t("failed", msg), "error")
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text=t("gen_failed"))
        if hasattr(self, 'progress_bar'):
            self.progress_bar["value"] = 0
        messagebox.showerror(t("gen_failed"), msg)

    def _on_finish(self):
        try:
            if self.generating: self.generating = False
            self._lock_ui(False)
        except Exception: pass


    def _start_update_check(self, force=False):
        """异步检测版本更新，保证同一时间只有一次检查。"""
        if self._update_checking:
            return
        if self._update_checked and not force:
            return
        self._update_checking = True
        self._update_request_id += 1
        request_id = self._update_request_id
        self._pending_update_result = None
        self.update_label.config(text="检查更新...", fg="#888888")

        # Tk calls from a worker thread can be dropped before mainloop starts.
        # Keep the network callback data-only and let the UI thread poll it.
        def _receive_result(latest_ver, update_info):
            self._pending_update_result = (request_id, latest_ver, update_info)

        check_for_update(VERSION, _receive_result)
        deadline = time.monotonic() + 22.0
        self.root.after(100, lambda: self._poll_update_result(request_id, deadline))

    def _poll_update_result(self, request_id, deadline):
        if request_id != self._update_request_id:
            return
        pending = self._pending_update_result
        if pending is not None and pending[0] == request_id:
            self._pending_update_result = None
            self._on_update_result(pending[1], pending[2])
            return
        if not self._update_checking:
            return
        if time.monotonic() >= deadline:
            self._update_checking = False
            self._update_checked = True
            self.update_label.config(text="更新检查超时（点击重试）", fg="#c77700")
            return
        try:
            self.root.after(100, lambda: self._poll_update_result(request_id, deadline))
        except tk.TclError:
            self._update_checking = False

    def _on_update_result(self, latest_ver, update_info=None):
        def _show_dialog():
            self._update_checking = False
            self._update_checked = True
            update_info = update_info or {}
            if not latest_ver:
                if update_info.get("error"):
                    self.update_label.config(text="更新检查失败（点击重试）", fg="#c77700")
                else:
                    self.update_label.config(text=f"当前已是最新版本 v{VERSION}", fg="#888888")
                return
            self.update_label.config(text=f"发现新版本 v{latest_ver}", fg="#2196F3")
            top = tk.Toplevel(self.root)
            top.title("发现新版本")
            top.configure(bg="#ffffff")
            w, h = 380, 200
            sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
            top.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            top.resizable(False, False)
            top.transient(self.root)
            top.grab_set()

            tk.Label(top, text=f"发现新版本 v{latest_ver}！",
                     font=("Microsoft YaHei", 14, "bold"),
                     fg="#333333", bg="#ffffff").pack(pady=(20, 5))
            tk.Label(top, text="请选择下载方式：",
                     font=("Microsoft YaHei", 10),
                     fg="#666666", bg="#ffffff").pack(pady=(0, 15))

            btn_frame = tk.Frame(top, bg="#ffffff")
            btn_frame.pack(pady=(5, 10))

            def _github():
                webbrowser.open(update_info.get("github_url") or "https://github.com/Bluelgin/AutoFTBQ/releases/latest")
                top.destroy()

            def _quark():
                webbrowser.open(update_info.get("quark_url") or QUARK_FALLBACK_URL)
                top.destroy()

            tk.Button(btn_frame, text="GitHub 更新", font=("Microsoft YaHei", 10),
                      fg="#ffffff", bg="#2196F3", bd=0, padx=16, pady=4,
                      command=_github).pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(btn_frame, text="夸克网盘更新", font=("Microsoft YaHei", 10),
                      fg="#ffffff", bg="#ff9800", bd=0, padx=16, pady=4,
                      command=_quark).pack(side=tk.LEFT, padx=(8, 0))
            tk.Button(btn_frame, text="稍后再说", font=("Microsoft YaHei", 10),
                      fg="#666666", bg="#e0e0e0", bd=0, padx=12, pady=4,
                      command=top.destroy).pack(side=tk.LEFT, padx=(8, 0))

        _show_dialog()

    def _on_update_click(self, event):
        self._start_update_check(force=True)

    def _center_window(self):
        self.root.update_idletasks()
        w,h = self.root.winfo_width(), self.root.winfo_height()
        sw,sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def on_close(self):
        if self.generating:
            if not messagebox.askyesno("Confirm", t("close_confirm")): return
        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            if width > 1 and height > 1:
                self.config["window_size"] = [width, height]
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        self.root.destroy()

def main():
    root = tk.Tk(); App(root); root.mainloop()

if __name__ == "__main__": main()
