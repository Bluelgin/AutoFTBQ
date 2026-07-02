#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoFTBQ - MC FTB Quest Book Generator"""

import os, sys, json, subprocess, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

APP_NAME = "AutoFTBQ"; VERSION = "1.3.0"; AUTHOR = "Taki"
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

AI_AVAILABLE = False; AI_IMPORT_ERROR = ""
scan_mod_folder = None; generate_quest_book = None
build_full_prompt = None; import_json_to_snbt = None

LANG = "zh"

# Ollama状态
ollama_available = False
ollama_models = []
ollama_best_model = None

CAT_LABEL = {"vanilla":"原版","tech":"科技","magic":"魔法","world":"维度/Boss","mob":"生物","utility":"辅助","food":"食物","decor":"装饰","unknown":"未知"}

T = {
    "zh": {
        "title": "AutoFTBQ - MC FTB任务书生成器",
        "subtitle": "选择 Mod → AI 生成完整任务指南",
        "subtitle_api": "API 模式 — DeepSeek / Ollama 自动生成",
        "subtitle_import": "导入模式 — 网页AI生成后粘贴JSON",
        "api_key": "API Key (DeepSeek)", "api_desc": "输入 DeepSeek API Key",
        "mod_folder": "Mod 文件夹", "mod_desc": "选择包含 .jar / .zip Mod 的文件夹",
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
        "api_key": "API Key (DeepSeek)", "api_desc": "Enter DeepSeek API Key",
        "mod_folder": "Mod Folder", "mod_desc": "Select .jar / .zip folder",
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
    try: import requests
    except ImportError: AI_IMPORT_ERROR = t("dep_msg"); return False
    try:
        import ai_module, importlib
        importlib.reload(ai_module)
        scan_mod_folder = ai_module.scan_mod_folder
        generate_quest_book = ai_module.generate_quest_book
        build_full_prompt = ai_module.build_full_prompt
        import_json_to_snbt = ai_module.import_json_to_snbt
        AI_AVAILABLE = True; return True
    except Exception as e: AI_IMPORT_ERROR = str(e); return False

class ModSelectDialog(tk.Toplevel):
    def __init__(self, parent, mods):
        super().__init__(parent)
        self.title("选择要生成任务书的 Mod")
        self.geometry("620x480")
        self.resizable(False, False)
        self.configure(bg="#ffffff")
        self.result = []

        try:
            tk.Label(self, text="勾选要包含在任务书中的 Mod：",
                     font=("Microsoft YaHei", 12, "bold"), bg="#ffffff", fg="#333333").pack(pady=(15, 5))
            tk.Label(self, text=f"检测到 {len(mods)} 个Mod — 请选择需要的Mod（可多选）",
                     font=("Microsoft YaHei", 9), bg="#ffffff", fg="#888888").pack(pady=(0, 10))

            frame = tk.Frame(self, bg="#ffffff")
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self._lb = tk.Listbox(frame, selectmode="multiple", yscrollcommand=scrollbar.set,
                                  font=("Microsoft YaHei", 9), bg="#ffffff", fg="#333333",
                                  activestyle="none", exportselection=False)
            self._lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=self._lb.yview)
            self._mods = mods
            for i, m in enumerate(mods):
                cat_cn = CAT_LABEL.get(m.get("category", "unknown"), "?")
                size_mb = m.get("size", 0) / (1024*1024)
                label = f"{m['mod_name']:30s} [{cat_cn}]  ({size_mb:.1f}MB)"
                self._lb.insert(tk.END, label)

            btnf = tk.Frame(self, bg="#ffffff")
            btnf.pack(fill=tk.X, pady=(0, 15), padx=20)
            tk.Button(btnf, text="全选", command=self._select_all, bg="#e0e0e0",
                      font=("Microsoft YaHei", 10), padx=10).pack(side=tk.LEFT)
            tk.Button(btnf, text="确定", command=self._on_ok, bg="#4caf50", fg="#ffffff",
                      font=("Microsoft YaHei", 11, "bold"), padx=30, pady=5).pack(side=tk.RIGHT)
            tk.Button(btnf, text="取消", command=self._on_cancel, bg="#cccccc", fg="#ffffff",
                      font=("Microsoft YaHei", 11), padx=20, pady=5).pack(side=tk.RIGHT, padx=(0, 10))

            self.transient(parent)
            self.grab_set()
            self.protocol("WM_DELETE_WINDOW", self._on_cancel)
            self._center(parent)
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

    def _select_all(self):
        self._lb.selection_set(0, tk.END)

    def _on_ok(self):
        selected = self._lb.curselection()
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个 Mod。")
            return
        self.result = [self._mods[i]["filename"] for i in selected]
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


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
            tk.Label(card1, text="填写 DeepSeek API Key 或使用本地 Ollama，"
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
        self.root.resizable(False, False)
        self.root.configure(bg="#ffffff")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = self._load_config()
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.mod_folder_var = tk.StringVar(value=self.config.get("mod_folder", ""))
        self.engine_var = tk.StringVar(value=self.config.get("engine", "deepseek"))
        self.ollama_model_var = tk.StringVar(value=self.config.get("ollama_model", ""))
        self.output_dir_var = tk.StringVar(value=self.config.get("output_dir", ""))
        self.use_wiki_var = tk.BooleanVar(value=self.config.get("use_wiki", False))
        self.generating = False
        self.selected_mods = []
        self._detected_mods = []

        self._build_ui()
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
        self._check_config_ready()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {}

    def _save_config(self):
        self.config["api_key"] = self.api_key_var.get().strip()
        self.config["mod_folder"] = self.mod_folder_var.get().strip()
        self.config["engine"] = self.engine_var.get()
        self.config["ollama_model"] = self.ollama_model_var.get()
        self.config["output_dir"] = self.output_dir_var.get().strip()
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

    def _build_ui(self):
        try:
            df = ("Microsoft YaHei", 10); tf = ("Microsoft YaHei", 26, "bold")
            sf = ("Microsoft YaHei", 9); bf = ("Microsoft YaHei", 11, "bold")
        except Exception:
            df = ("TkDefaultFont", 10); tf = ("TkDefaultFont", 26, "bold")
            sf = ("TkDefaultFont", 9); bf = ("TkDefaultFont", 11, "bold")

        # 窗口大小根据模式调整
        if self.mode == "api":
            self.root.geometry("780x850")
        else:
            self.root.geometry("680x780")

        mf = tk.Frame(self.root, bg="#ffffff", padx=30, pady=20)
        mf.pack(fill=tk.BOTH, expand=True)

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
        self.mod_status_label = tk.Label(sec2, font=sf, fg="#888888", bg="#ffffff")
        self.mod_status_label.pack(anchor=tk.W, pady=(4, 0))

        # ── 输出目录（两种模式共用） ──
        sec3 = tk.Frame(mf, bg="#ffffff"); sec3.pack(fill=tk.X, pady=(0, 10))
        tk.Label(sec3, text="输出目录 (可选)", font=("Microsoft YaHei", 10, "bold"),
                 fg="#555555", bg="#ffffff").pack(anchor=tk.W)
        tk.Label(sec3, text="留空则保存到软件目录下的 questbook_output 文件夹",
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

        self.footer_label = tk.Label(mf, font=("Microsoft YaHei", 8), fg="#cccccc", bg="#ffffff")
        self.footer_label.pack(pady=(15, 0))

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
        self.show_btn = tk.Button(row, font=sf, width=5, command=self._toggle_key_vis, bg="#f0f0f0", fg="#555555", bd=1, relief=tk.SOLID, cursor="hand2", activebackground="#e0e0e0")
        self.show_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self._key_visible = False

        # ── Engine Selector ──
        self.engine_frame = tk.Frame(mf, bg="#ffffff")
        self.engine_frame.pack(fill=tk.X, pady=(0, 12))
        self.engine_label = tk.Label(self.engine_frame, text="AI引擎:", font=("Microsoft YaHei", 10, "bold"), fg="#555555", bg="#ffffff")
        self.engine_label.pack(side=tk.LEFT, padx=(0, 10))
        self.engine_ds_btn = tk.Button(self.engine_frame, text="DeepSeek API", font=("Microsoft YaHei", 10),
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

        # ── Wiki 增强复选框 ──
        wiki_row = tk.Frame(mf, bg="#ffffff")
        wiki_row.pack(fill=tk.X, pady=(0, 6))
        self.use_wiki_check = tk.Checkbutton(wiki_row, text="使用 MC百科 Wiki 数据增强（需要网络）",
                                              variable=self.use_wiki_var, font=("Microsoft YaHei", 9),
                                              fg="#666666", bg="#ffffff", activebackground="#ffffff",
                                              selectcolor="#ffffff", command=self._save_config)
        self.use_wiki_check.pack(side=tk.LEFT)

        ttk.Separator(mf, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 15))

        # Progress
        pf = tk.Frame(mf, bg="#ffffff"); pf.pack(fill=tk.X, pady=(0, 10))
        self.progress_label = tk.Label(pf, text="", font=sf, fg="#888888", bg="#ffffff", anchor=tk.W)
        self.progress_label.pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(pf, mode="determinate", length=620, value=0)
        self.progress_bar.pack(fill=tk.X, pady=(4, 0))

        # Info
        self.info_frame = tk.Frame(mf, bg="#f8f8f8", padx=15, pady=12)
        self.info_frame.pack(fill=tk.X, pady=(0, 15))
        self.info_label = tk.Label(self.info_frame, font=sf, fg="#888888", bg="#f8f8f8", wraplength=600, justify=tk.LEFT)
        self.info_label.pack(anchor=tk.W)

        # Buttons
        btnf = tk.Frame(mf, bg="#ffffff"); btnf.pack(fill=tk.X)
        self.save_btn = tk.Button(btnf, font=bf, command=self._on_save_config, bg="#4a90d9", fg="#ffffff", bd=0, relief=tk.FLAT, cursor="hand2", activebackground="#357abd", activeforeground="#ffffff", padx=20, pady=8)
        self.save_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.generate_btn = tk.Button(btnf, font=bf, command=self._on_generate, bg="#cccccc", fg="#ffffff", bd=0, relief=tk.FLAT, cursor="hand2", activebackground="#cccccc", activeforeground="#ffffff", padx=20, pady=8, state=tk.DISABLED)
        self.generate_btn.pack(side=tk.RIGHT)

    def _build_import_specific(self, mf, df):
        """构建导入模式专属 UI"""
        # Info
        self.info_frame = tk.Frame(mf, bg="#f0faf0", padx=15, pady=12)
        self.info_frame.pack(fill=tk.X, pady=(0, 12))
        self.info_label = tk.Label(self.info_frame, font=("Microsoft YaHei", 9), fg="#4caf50", bg="#f0faf0", wraplength=580, justify=tk.LEFT,
                                    text="💡 提示：先选 Mod → 点「保存提示词」→ 上传文件到网页AI → 粘贴返回的JSON → 点「生成SNBT」")
        self.info_label.pack(anchor=tk.W)

        # JSON 输入区（增大）
        json_label = tk.Label(mf, text="粘贴 AI 返回的 JSON：",
                               font=("Microsoft YaHei", 12, "bold"), fg="#333333", bg="#ffffff")
        json_label.pack(anchor=tk.W, pady=(0, 4))
        self.json_text = tk.Text(mf, height=8, font=("Consolas", 10),
                                  bg="#fafafa", fg="#333333", bd=1, relief=tk.SOLID,
                                  wrap=tk.WORD)
        self.json_text.pack(fill=tk.X)

        # Buttons
        btnf = tk.Frame(mf, bg="#ffffff")
        btnf.pack(fill=tk.X, pady=(10, 0))
        self.save_prompt_api_btn = tk.Button(btnf, text="📤 保存提示词文件", font=("Microsoft YaHei", 10),
                                              command=self._on_save_prompt, bg="#2196f3", fg="#ffffff",
                                              bd=0, relief=tk.FLAT, cursor="hand2",
                                              activebackground="#1976d2", activeforeground="#ffffff",
                                              padx=14, pady=8, state=tk.DISABLED)
        self.save_prompt_api_btn.pack(side=tk.LEFT)
        self.import_btn = tk.Button(btnf, text="📄 粘贴并生成 SNBT", font=("Microsoft YaHei", 11, "bold"),
                                     command=self._on_import_json, bg="#4caf50", fg="#ffffff",
                                     bd=0, relief=tk.FLAT, cursor="hand2",
                                     activebackground="#388e3c", activeforeground="#ffffff",
                                     padx=20, pady=8)
        self.import_btn.pack(side=tk.RIGHT)

        # Progress (简化)
        self.progress_label = tk.Label(mf, text="", font=("Microsoft YaHei", 9), fg="#888888", bg="#ffffff", anchor=tk.W)
        self.progress_label.pack(anchor=tk.W, pady=(10, 0))
        self.progress_bar = ttk.Progressbar(mf, mode="determinate", length=620, value=0)
        self.progress_bar.pack(fill=tk.X, pady=(6, 0))

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
            self.mod_folder_var.set(folder)
            self.selected_mods = []
            if hasattr(self, 'save_prompt_api_btn'):
                self.save_prompt_api_btn.config(state=tk.DISABLED)
            try:
                self._detected_mods = scan_mod_folder(folder)
                n = len(self._detected_mods)
                self.mod_status_label.config(text=f"检测到 {n} 个Mod  |  已选: 0", fg="#888888")
                if n:
                    self.set_info(t("found_mods", n), "success")
                else:
                    self.set_info(t("no_mods"), "warning")
            except Exception as e:
                self.set_info(f"{t('dir_error')}: {e}", "error")
            self._check_config_ready()

    def _open_mod_select(self):
        if scan_mod_folder is None:
            messagebox.showwarning("Warning", "依赖未就绪，请稍等。")
            return
        if not self._detected_mods:
            messagebox.showinfo("Info", "请先选择Mod文件夹。")
            return
        dlg = ModSelectDialog(self.root, self._detected_mods)
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
        self._check_config_ready()

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
            self.info_label.config(fg=fg); self.info_frame.config(bg=bg)

    def _on_progress(self, msg, pct):
        if not self.generating: return
        self.root.after(0, self._set_progress_ui, msg, pct)

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
            if hasattr(self, 'save_prompt_api_btn'):
                self.save_prompt_api_btn.config(state=s)
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
        if engine == "deepseek" and not api_key:
            messagebox.showwarning("Warning", t("enter_api")); return
        if engine == "ollama" and not ollama_available:
            messagebox.showwarning("Warning", "Ollama未运行。请先启动Ollama，或切换到DeepSeek API。"); return
        if not self.selected_mods: messagebox.showwarning("Warning", "请点击「选择 Mod」勾选要生成的Mod"); return
        if not messagebox.askokcancel(t("confirm_title"), t("confirm_msg", len(self.selected_mods))): return
        self._save_config(); self.generating = True; self._lock_ui(True)
        self.set_info(t("preparing"), "info")
        mf = self.mod_folder_var.get().strip()
        threading.Thread(target=self._generate_thread, args=(
            api_key if engine == "deepseek" else None,
            list(self.selected_mods), LANG, engine,
            self.ollama_model_var.get().strip(),
            self.output_dir_var.get().strip() or None,
            bool(self.use_wiki_var.get()),
        ), daemon=True).start()

    def _generate_thread(self, api_key, selected_mods, lang, engine, ollama_model, output_dir, use_wiki=False):
        try:
            mf = self.mod_folder_var.get().strip()
            out = generate_quest_book(
                api_key=api_key, selected_mods=selected_mods,
                mod_folder=mf, progress_callback=self._on_progress,
                lang=lang, engine=engine, ollama_model=ollama_model, output_dir=output_dir,
                use_wiki=use_wiki
            )
            self.root.after(0, self._on_done, out)
        except Exception as e: self.root.after(0, self._on_fail, str(e))
        finally: self.generating = False; self.root.after(0, self._on_finish)

    def _on_done(self, path):
        self.set_info("Done!", "success")
        if hasattr(self, 'progress_bar'):
            self.progress_bar["value"] = 100
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text="Done!")
        if messagebox.askyesno(t("success_title"), t("success_msg", path)):
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

    def _center_window(self):
        self.root.update_idletasks()
        w,h = self.root.winfo_width(), self.root.winfo_height()
        sw,sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def on_close(self):
        if self.generating:
            if not messagebox.askyesno("Confirm", t("close_confirm")): return
        self.root.destroy()

def main():
    root = tk.Tk(); App(root); root.mainloop()

if __name__ == "__main__": main()