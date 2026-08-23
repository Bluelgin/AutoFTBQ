"""Minecraft instance detection and safe AutoFTBQ output defaults."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sys


@dataclass(frozen=True)
class InstanceInfo:
    root: str
    mods_dir: str
    quests_dir: str
    minecraft_version: str = ""
    loader: str = ""
    ftb_quests_version: str = ""


def application_dir(resource_dir: str) -> str:
    """Return a persistent directory instead of PyInstaller's temporary _MEI path."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(resource_dir)


def _instance_paths(selected_path: str) -> tuple[str, str]:
    path = os.path.abspath(selected_path)
    nested_mods = os.path.join(path, "mods")
    if os.path.isdir(nested_mods):
        return path, nested_mods
    if os.path.basename(path).lower() == "mods":
        return os.path.dirname(path), path
    return path, path


def _version_metadata(root: str) -> tuple[str, str]:
    minecraft_version = ""
    loader = ""
    try:
        filenames = sorted(os.listdir(root)) if os.path.isdir(root) else []
    except OSError:
        filenames = []
    for filename in filenames:
        if not filename.lower().endswith(".json"):
            continue
        path = os.path.join(root, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        serialized = json.dumps(payload, ensure_ascii=True).lower()
        arguments_block = payload.get("arguments")
        arguments = arguments_block.get("game", []) if isinstance(arguments_block, dict) else []
        if isinstance(arguments, list):
            for index, value in enumerate(arguments[:-1]):
                if value == "--fml.mcVersion":
                    minecraft_version = str(arguments[index + 1])
                    break
        if not minecraft_version:
            candidate = str(payload.get("inheritsFrom", "") or payload.get("id", ""))
            match = re.search(r"(?<!\d)(1\.\d+(?:\.\d+)?)(?!\d)", candidate)
            if match:
                minecraft_version = match.group(1)
        if "neoforge" in serialized:
            loader = "NeoForge"
        elif "net.minecraftforge" in serialized or "forgeclient" in serialized:
            loader = "Forge"
        elif "fabric-loader" in serialized or "fabricloader" in serialized:
            loader = "Fabric"
        elif "quilt-loader" in serialized or "quiltloader" in serialized:
            loader = "Quilt"
        if minecraft_version or loader:
            break
    return minecraft_version, loader


def _ftb_quests_version(mods_dir: str) -> str:
    if not os.path.isdir(mods_dir):
        return ""
    try:
        filenames = sorted(os.listdir(mods_dir))
    except OSError:
        return ""
    for filename in filenames:
        lower = filename.lower()
        if "ftb-quests" not in lower and "ftbquests" not in lower:
            continue
        match = re.search(r"(?:ftb-?quests(?:-forge|-fabric|-neoforge)?)[-_]([0-9][0-9a-z.+-]*)", lower)
        return match.group(1).removesuffix(".jar") if match else filename
    return ""


def resolve_instance(selected_path: str) -> InstanceInfo | None:
    """Resolve a selected pack root or mods directory into instance metadata."""
    if not selected_path or not os.path.isdir(selected_path):
        return None
    root, mods_dir = _instance_paths(selected_path)
    minecraft_version, loader = _version_metadata(root)
    return InstanceInfo(
        root=root,
        mods_dir=mods_dir,
        quests_dir=os.path.join(root, "config", "ftbquests", "quests"),
        minecraft_version=minecraft_version,
        loader=loader,
        ftb_quests_version=_ftb_quests_version(mods_dir),
    )


def suggested_output_dir(selected_path: str) -> str:
    """Suggest the real instance quest directory when the selection is recognizable."""
    info = resolve_instance(selected_path)
    if info is None:
        return ""
    has_instance_markers = any(
        os.path.exists(os.path.join(info.root, marker))
        for marker in ("config", "kubejs", "saves", "logs")
    )
    return info.quests_dir if has_instance_markers else ""
