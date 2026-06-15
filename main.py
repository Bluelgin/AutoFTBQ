#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoFTBQ - MC FTB Quest Book Generator"""

import os, sys, json, subprocess, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

APP_NAME = "AutoFTBQ"; VERSION = "1.1.1"; AUTHOR = "Taki"
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

AI_AVAILABLE = False; AI_IMPORT_ERROR = ""
scan_mod_folder = None; generate_quest_book = None

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
    try: import requests
    except ImportError: AI_IMPORT_ERROR = t("dep_msg"); return False
    try:
        import ai_module, importlib
        importlib.reload(ai_module)
        scan_mod_folder = ai_module.scan_mod_folder
        generate_quest_book = ai_module.generate_quest_book
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

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION} - {AUTHOR}")
        self.root.geometry("680x630")
        self.root.resizable(False, False)
        self.root.configure(bg="#ffffff")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = self._load_config()
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.mod_folder_var = tk.StringVar(value=self.config.get("mod_folder", ""))
        self.engine_var = tk.StringVar(value=self.config.get("engine", "deepseek"))
        self.ollama_model_var = tk.StringVar(value=self.config.get("ollama_model", ""))
        self.generating = False
        self.selected_mods = []
        self._detected_mods = []

        self._build_ui()
        self._center_window()
        self._refresh_text()
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
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e: messagebox.showerror("Error", str(e)); return False

    def _check_config_ready(self):
        engine = self.engine_var.get()
        mf = self.mod_folder_var.get().strip()
        if not AI_AVAILABLE: self.generate_btn.config(state=tk.DISABLED, bg="#cccccc"); self.set_info(t("deps_missing"), "error"); return
        if not mf or not os.path.isdir(mf): self.generate_btn.config(state=tk.DISABLED, bg="#cccccc"); self.set_info(t("select_mod"), "warning"); return
        if not self.selected_mods: self.generate_btn.config(state=tk.DISABLED, bg="#cccccc"); self.set_info(t("ready"), "info"); return
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
        global ollama_available, ollama_best_model, ollama_models
        engine = self.engine_var.get()
        if engine == "ollama":
            self.engine_ds_btn.config(bg="#e0e0e0", fg="#555555")
            self.engine_ollama_btn.config(bg="#4caf50", fg="#ffffff")
            # 隐藏API Key框（整块隐藏）
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
            # 恢复API Key框（插在engine_frame上方）
            self.api_frame.pack(before=self.engine_frame, fill=tk.X, pady=(0, 15))

    def _build_ui(self):
        try:
            df = ("Microsoft YaHei", 10); tf = ("Microsoft YaHei", 26, "bold")
            sf = ("Microsoft YaHei", 9); bf = ("Microsoft YaHei", 11, "bold")
        except Exception:
            df = ("TkDefaultFont", 10); tf = ("TkDefaultFont", 26, "bold")
            sf = ("TkDefaultFont", 9); bf = ("TkDefaultFont", 11, "bold")

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

        # ── API Key (可隐藏) ──
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

        # ── Mod Folder ──
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

        # ═══ Engine Selector ═══
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

        self.footer_label = tk.Label(mf, font=("Microsoft YaHei", 8), fg="#cccccc", bg="#ffffff")
        self.footer_label.pack(pady=(15, 0))

    def _browse_mod_folder(self):
        if scan_mod_folder is None:
            messagebox.showwarning("Warning", "请在依赖检查完成后再操作。")
            return
        folder = filedialog.askdirectory(title=t("mod_folder"))
        if folder:
            self.mod_folder_var.set(folder)
            self.selected_mods = []
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
        self._check_config_ready()

    def _refresh_text(self):
        self.subtitle_label.config(text=t("subtitle"))
        self.api_label.config(text=t("api_key"))
        self.api_desc_label.config(text=t("api_desc"))
        self.mod_label.config(text=t("mod_folder"))
        self.mod_desc_label.config(text=t("mod_desc"))
        self.browse_btn.config(text=t("browse"))
        self.select_mods_btn.config(text=t("select_mods"))
        self.save_btn.config(text=t("save_config"))
        self.lang_btn.config(text=t("lang"))
        self.show_btn.config(text=t("hide") if self._key_visible else t("show"))
        self.generate_btn.config(text=t("generating") if self.generating else t("generate"))
        self.footer_label.config(text=f"v{VERSION}  |  {t('author_line')}  |  {t('powered')}")
        self._check_config_ready()

    def _toggle_lang(self):
        global LANG
        LANG = "en" if LANG == "zh" else "zh"
        self._refresh_text()

    def _toggle_key_vis(self):
        self._key_visible = not self._key_visible
        self.api_entry.config(show="" if self._key_visible else "*")
        self.show_btn.config(text=t("hide") if self._key_visible else t("show"))

    def set_info(self, text, level="info"):
        self.info_label.config(text=text)
        c = {"success":("#4caf50","#f0faf0"),"warning":("#ff9800","#fffaf0"),"error":("#f44336","#fff5f5")}
        fg,bg = c.get(level,("#888888","#f8f8f8"))
        self.info_label.config(fg=fg); self.info_frame.config(bg=bg)

    def _on_progress(self, msg, pct):
        if not self.generating: return
        self.root.after(0, self._set_progress_ui, msg, pct)

    def _set_progress_ui(self, msg, pct):
        try: self.progress_label.config(text=msg); self.progress_bar["value"]=pct; self.set_info(msg,"info")
        except Exception: pass

    def _lock_ui(self, locked):
        s = tk.DISABLED if locked else tk.NORMAL
        try:
            self.api_entry.config(state=s); self.show_btn.config(state=s)
            self.mod_entry.config(state="readonly" if not locked else tk.DISABLED)
            self.browse_btn.config(state=s); self.save_btn.config(state=s)
            self.lang_btn.config(state=s); self.select_mods_btn.config(state=s)
        except Exception: pass
        if locked: self.generate_btn.config(text=t("generating"), state=tk.DISABLED, bg="#ff9800", activebackground="#ff9800")
        else: self._check_config_ready(); self.generate_btn.config(text=t("generate")); self.progress_label.config(text=""); self.progress_bar["value"]=0

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
            self.ollama_model_var.get().strip()
        ), daemon=True).start()

    def _generate_thread(self, api_key, selected_mods, lang, engine, ollama_model):
        try:
            mf = self.mod_folder_var.get().strip()
            out = generate_quest_book(
                api_key=api_key, selected_mods=selected_mods,
                mod_folder=mf, progress_callback=self._on_progress,
                lang=lang, engine=engine, ollama_model=ollama_model
            )
            self.root.after(0, self._on_done, out)
        except Exception as e: self.root.after(0, self._on_fail, str(e))
        finally: self.generating = False; self.root.after(0, self._on_finish)

    def _on_done(self, path):
        self.set_info("Done!", "success"); self.progress_bar["value"]=100; self.progress_label.config(text="Done!")
        if messagebox.askyesno(t("success_title"), t("success_msg", path)):
            try: os.startfile(path)
            except Exception: subprocess.Popen(["explorer", path], shell=True)

    def _on_fail(self, msg):
        self.set_info(t("failed", msg), "error"); self.progress_label.config(text=t("gen_failed"))
        self.progress_bar["value"]=0; messagebox.showerror(t("gen_failed"), msg)

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