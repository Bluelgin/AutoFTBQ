"""Regenerate the questbook for the configured modpack and polish it.

Reads config.json, scans the mod folder, generates a theme-based questbook,
re-lays-out coordinates and AI-polishes the wording (when enabled), then
writes the SNBT files to the configured output directory.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    if os.environ.get("POLISH_LOG"):
        log_path = os.environ["POLISH_LOG"]
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
            sys.stdout = open(log_path, "w", encoding="utf-8")
            sys.stderr = sys.stdout
        except Exception as exc:
            print(f"[WARN] cannot open log {log_path}: {exc}")

    os.environ["NO_PROXY"] = "api.deepseek.com"
    os.environ["no_proxy"] = "api.deepseek.com"

    import ai_module as am

    config_path = "config.json"
    with open(config_path, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    mod_folder = config.get("mod_folder", "")
    if not mod_folder or not os.path.isdir(mod_folder):
        print(f"[ERROR] mod folder not found: {mod_folder}")
        sys.exit(1)

    print(f"[INFO] scanning mods from {mod_folder}", flush=True)
    mods = am.scan_mod_folder(mod_folder)
    if not mods:
        print("[ERROR] no mods found")
        sys.exit(1)
    selected = list(mods)
    print(f"[INFO] selected {len(selected)} mod files", flush=True)

    def progress(message: str, percent=None) -> None:
        print(f"[PROGRESS {percent}] {message}", flush=True)

    output_dir = config.get("output_dir") or None
    print(f"[INFO] generating questbook (density={config.get('density', 'max')})...", flush=True)
    saved = am.generate_quest_book(
        api_key=config.get("api_key"),
        selected_mods=selected,
        mod_folder=mod_folder,
        progress_callback=progress,
        lang="zh",
        engine=config.get("engine", "deepseek"),
        ollama_model=config.get("ollama_model"),
        output_dir=output_dir,
        provider=config.get("provider", "DeepSeek"),
        api_url=config.get("api_url", ""),
        api_model=config.get("api_model", ""),
        density=config.get("density", "max"),
        max_output_tokens=None,
        polish_after_generate=bool(config.get("polish_after_generate", False)),
        auto_complete=bool(config.get("api_url_auto_complete", True)),
    )
    print(f"[INFO] done, output: {saved}", flush=True)


if __name__ == "__main__":
    main()
