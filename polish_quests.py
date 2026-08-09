"""Command-line tool: re-layout and/or AI-polish an existing questbook.

Examples:
    python polish_quests.py --input quests --output questbook_output
    python polish_quests.py --input quests --in-place --polish
    python polish_quests.py --input quests --dry-run --polish
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import ai_clients  # noqa: F401  (ensures the package path is importable)

from snbt_parser import parse_snbt, to_snbt
from quest_layout import relayout_chapter
from quest_polish import QuestPolishService
from human_corpus import HumanQuestCorpus


def _load_config(config_path: str) -> dict:
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            print(f"[WARN] 无法读取配置 {config_path}: {exc}")
    return {}


def _create_client(config: dict):
    from ai_clients import create_chat_client

    engine = str(config.get("engine", "deepseek"))
    return create_chat_client(
        engine=engine,
        api_key=config.get("api_key"),
        ollama_model=config.get("ollama_model"),
        provider=config.get("provider"),
        api_url=config.get("api_url"),
        api_model=config.get("api_model"),
    )


def load_chapters(input_dir: str) -> list[dict]:
    chapters_dir = os.path.join(input_dir, "chapters")
    if not os.path.isdir(chapters_dir):
        print(f"[ERROR] 找不到章节目录: {chapters_dir}")
        sys.exit(1)
    chapters = []
    for filename in sorted(os.listdir(chapters_dir)):
        if not filename.endswith(".snbt"):
            continue
        path = os.path.join(chapters_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = parse_snbt(handle.read())
        except Exception as exc:
            print(f"[WARN] 解析失败，跳过 {filename}: {exc}")
            continue
        if isinstance(data, dict):
            chapters.append({"chapter": data, "filename": filename})
    print(f"[INFO] 读取到 {len(chapters)} 个章节")
    return chapters


def _copy_support_files(input_dir: str, output_dir: str) -> None:
    for name in ("data.snbt", "chapter_groups.snbt", "ai_raw_output.txt", "id_validation_report.txt"):
        source = os.path.join(input_dir, name)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(output_dir, name))
    source_rt = os.path.join(input_dir, "reward_tables")
    target_rt = os.path.join(output_dir, "reward_tables")
    if os.path.isdir(source_rt):
        os.makedirs(target_rt, exist_ok=True)
        for filename in os.listdir(source_rt):
            if filename.endswith(".snbt"):
                shutil.copy2(os.path.join(source_rt, filename), os.path.join(target_rt, filename))


def write_chapters(
    chapters: list[dict],
    output_dir: str,
    create_backup: bool = False,
    remove_stale: bool = False,
) -> str | None:
    payloads = {}
    for item in chapters:
        filename = item["filename"]
        payload = to_snbt(item["chapter"])
        # Refuse to touch the destination unless every chapter round-trips.
        if parse_snbt(payload) != item["chapter"]:
            raise ValueError(f"SNBT round-trip validation failed: {filename}")
        payloads[filename] = payload

    chapters_dir = os.path.join(output_dir, "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    backup_dir = None
    if create_backup and os.path.isdir(chapters_dir):
        backup_dir = os.path.join(
            output_dir,
            f"polish_backup_{time.strftime('%Y%m%d_%H%M%S')}",
            "chapters",
        )
        shutil.copytree(chapters_dir, backup_dir)

    staging_root = tempfile.mkdtemp(prefix=".polish-", dir=output_dir)
    try:
        staged_chapters = os.path.join(staging_root, "chapters")
        os.makedirs(staged_chapters, exist_ok=True)
        for filename, payload in payloads.items():
            staged_path = os.path.join(staged_chapters, filename)
            with open(staged_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
        for filename in payloads:
            os.replace(
                os.path.join(staged_chapters, filename),
                os.path.join(chapters_dir, filename),
            )
        if remove_stale:
            for filename in os.listdir(chapters_dir):
                if filename.endswith(".snbt") and filename not in payloads:
                    os.remove(os.path.join(chapters_dir, filename))
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    return backup_dir


def main() -> None:
    # Optional in-process logging so background runs are observable without
    # relying on shell-level stdout redirection.
    if os.environ.get("POLISH_LOG"):
        log_path = os.environ["POLISH_LOG"]
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
            log_handle = open(log_path, "w", encoding="utf-8")
            sys.stdout = log_handle
            sys.stderr = log_handle
        except Exception as exc:
            print(f"[WARN] 无法打开日志文件 {log_path}: {exc}")

    # Bypass the local system proxy (nano.exe accelerator) for the DeepSeek
    # endpoint; proxied long-running requests have been observed to stall.
    os.environ["NO_PROXY"] = "api.deepseek.com"
    os.environ["no_proxy"] = "api.deepseek.com"

    parser = argparse.ArgumentParser(description="重排/润色 FTB Quests 任务书")
    parser.add_argument("--input", default="quests", help="现有任务书目录(含 chapters/)")
    parser.add_argument("--output", default="", help="输出目录(默认 questbook_output)")
    parser.add_argument("--in-place", action="store_true", help="直接修改输入目录")
    parser.add_argument("--polish", action="store_true", help="启用 AI 文案润色")
    parser.add_argument("--no-layout", action="store_true", help="跳过布局重排")
    parser.add_argument("--batch-size", type=int, default=12, help="润色每批任务数")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input)
    chapters = load_chapters(input_dir)
    if not chapters:
        print("[ERROR] 没有可处理的章节")
        sys.exit(1)

    if not args.no_layout:
        for item in chapters:
            relayout_chapter(item["chapter"])
        print("[INFO] 布局重排完成")

    polish_report = {}
    if args.polish:
        print("[INFO] 创建 AI 客户端...", flush=True)
        config = _load_config(args.config)
        client = _create_client(config)
        if client is None:
            print("[ERROR] 无法创建 AI 客户端，请检查 config.json")
            sys.exit(1)
        print("[INFO] 加载人工语料库...", flush=True)
        corpus = HumanQuestCorpus()
        print(f"[INFO] 语料库加载完成: {len(corpus.examples)} 条", flush=True)
        service = QuestPolishService(
            client,
            corpus=corpus,
            max_quests_per_batch=args.batch_size,
        )
        for index, item in enumerate(chapters):
            chapter = item["chapter"]
            print(f"[INFO] 章节 {index + 1}/{len(chapters)}: {chapter.get('title', '')} 开始", flush=True)
            _, chapter_report = service.polish_chapter(chapter)
            print(
                f"[INFO] 章节 {index + 1}/{len(chapters)} 完成: "
                f"应用 {chapter_report.get('applied', 0)} 补丁，"
                f"跳过 {chapter_report.get('skipped', 0)} 已润色",
                flush=True,
            )
            polish_report[item["filename"]] = chapter_report
        print("[INFO] AI 润色完成")

    if args.dry_run:
        print("[INFO] dry-run: 未写入任何文件")
        if polish_report:
            total_applied = sum(r.get("applied", 0) for r in polish_report.values())
            total_warnings = sum(len(r.get("warnings", [])) for r in polish_report.values())
            print(f"[INFO] 预计润色 {total_applied} 个任务，{total_warnings} 条警告")
        return

    output_dir = input_dir if args.in_place else os.path.abspath(args.output or "questbook_output")
    if not args.in_place:
        os.makedirs(output_dir, exist_ok=True)
        _copy_support_files(input_dir, output_dir)
    backup_dir = write_chapters(
        chapters,
        output_dir,
        create_backup=args.in_place,
        remove_stale=not args.in_place,
    )
    print(f"[INFO] 已写入: {output_dir}")
    if backup_dir:
        print(f"[INFO] 原章节备份: {backup_dir}")

    if polish_report:
        report_lines = [
            "=== AI 润色报告 ===",
            "每章格式: 文件名 | 任务数 | 应用补丁数 | 警告",
        ]
        total_applied = 0
        total_quests = 0
        for filename, report in polish_report.items():
            applied = report.get("applied", 0)
            quests = report.get("quests", 0)
            warnings = "; ".join(report.get("warnings", [])) or "无"
            total_applied += applied
            total_quests += quests
            report_lines.append(f"{filename} | {quests} | {applied} | {warnings}")
        report_lines.append("")
        report_lines.append(f"合计: 润色 {total_applied}/{total_quests} 个任务")
        report_path = os.path.join(output_dir, "polish_report.txt")
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(report_lines))
        print(f"[INFO] 润色报告: {report_path}")


if __name__ == "__main__":
    main()
