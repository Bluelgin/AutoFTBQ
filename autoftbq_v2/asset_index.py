"""Offline item model and icon index for modpack projects."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import shutil
import zipfile


@dataclass(frozen=True)
class ResourceRef:
    source: str
    entry: str = ""

    @property
    def modified(self) -> int:
        try:
            return int(os.path.getmtime(self.source))
        except OSError:
            return 0

    def read(self, max_bytes: int = 8 * 1024 * 1024) -> bytes:
        if self.entry:
            with zipfile.ZipFile(self.source, "r") as archive:
                info = archive.getinfo(self.entry)
                if info.file_size > max_bytes:
                    raise ValueError(f"资源过大：{self.entry}")
                return archive.read(info)
        if os.path.getsize(self.source) > max_bytes:
            raise ValueError(f"资源过大：{self.source}")
        with open(self.source, "rb") as handle:
            return handle.read()


@dataclass
class ItemAsset:
    item_id: str
    name: str
    model_path: str = ""
    texture_path: str = ""
    icon_path: str = ""
    render_status: str = "missing"


class AssetIndex:
    """Layer Minecraft resources and lazily cache recognizable item icons."""

    def __init__(self, pack_root: str, cache_root: str):
        self.pack_root = os.path.abspath(pack_root)
        pack_key = hashlib.sha1(os.path.normcase(self.pack_root).encode("utf-8")).hexdigest()[:12]
        self.cache_dir = os.path.join(os.path.abspath(cache_root), pack_key)
        self.resources: dict[str, ResourceRef] = {}
        self.items: dict[str, ItemAsset] = {}

    @classmethod
    def build(cls, pack_root: str, all_items: dict, cache_root: str) -> "AssetIndex":
        index = cls(pack_root, cache_root)
        index._collect_resources()
        for namespace, values in all_items.items():
            if not isinstance(values, dict):
                continue
            for item_id, name in values.items():
                index.items[item_id] = ItemAsset(item_id=item_id, name=str(name))
        index._resolve_assets()
        return index

    @staticmethod
    def _resource_key(value: str) -> str:
        return str(value).replace("\\", "/").lstrip("/").lower()

    def _add_archive(self, path: str) -> None:
        try:
            with zipfile.ZipFile(path, "r") as archive:
                if len(archive.infolist()) > 250_000:
                    return
                for info in archive.infolist():
                    key = self._resource_key(info.filename)
                    if not key.startswith("assets/") or info.is_dir():
                        continue
                    if not (key.endswith(".json") or key.endswith(".png")):
                        continue
                    self.resources[key] = ResourceRef(path, info.filename)
        except (OSError, zipfile.BadZipFile):
            return

    def _add_directory(self, root: str) -> None:
        if not os.path.isdir(root):
            return
        for current, _dirs, files in os.walk(root):
            for filename in files:
                if not filename.lower().endswith((".json", ".png")):
                    continue
                path = os.path.join(current, filename)
                relative = self._resource_key(os.path.relpath(path, root))
                if relative.startswith("assets/"):
                    self.resources[relative] = ResourceRef(path)

    def _collect_resources(self) -> None:
        root = self.pack_root
        mods_dir = os.path.join(root, "mods") if os.path.isdir(os.path.join(root, "mods")) else root
        # Later layers override earlier ones, matching the useful subset of resource-pack behavior.
        if os.path.isdir(root):
            for filename in sorted(os.listdir(root)):
                if filename.lower().endswith(".jar"):
                    self._add_archive(os.path.join(root, filename))
        if os.path.isdir(mods_dir):
            for filename in sorted(os.listdir(mods_dir)):
                if filename.lower().endswith((".jar", ".zip")):
                    self._add_archive(os.path.join(mods_dir, filename))
        self._add_directory(os.path.join(root, "kubejs"))
        resourcepacks = os.path.join(root, "resourcepacks")
        if os.path.isdir(resourcepacks):
            for filename in sorted(os.listdir(resourcepacks)):
                path = os.path.join(resourcepacks, filename)
                if os.path.isdir(path):
                    self._add_directory(path)
                elif filename.lower().endswith(".zip"):
                    self._add_archive(path)

    def _json(self, path: str) -> dict:
        ref = self.resources.get(self._resource_key(path))
        if ref is None:
            return {}
        try:
            value = json.loads(ref.read().decode("utf-8-sig"))
            return value if isinstance(value, dict) else {}
        except (OSError, UnicodeError, ValueError, KeyError, zipfile.BadZipFile):
            return {}

    @staticmethod
    def _location(value: str, default_namespace: str, category: str, extension: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        namespace, path = raw.split(":", 1) if ":" in raw else (default_namespace, raw)
        path = path.removeprefix(f"{category}/")
        return f"assets/{namespace}/{category}/{path}{extension}"

    @staticmethod
    def _first_model(value) -> str:
        if isinstance(value, dict):
            model_type = str(value.get("type", ""))
            model = value.get("model")
            if isinstance(model, str) and (model_type.endswith(":model") or not model_type):
                return model
            for key in ("model", "fallback", "on_true", "on_false", "cases", "entries", "models"):
                found = AssetIndex._first_model(value.get(key))
                if found:
                    return found
            for nested in value.values():
                found = AssetIndex._first_model(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = AssetIndex._first_model(nested)
                if found:
                    return found
        return ""

    def _resolve_texture(self, item_id: str) -> tuple[str, str]:
        namespace, item_path = item_id.split(":", 1)
        direct = self._location(f"{namespace}:{item_path}", namespace, "textures/item", ".png")
        if self._resource_key(direct) in self.resources:
            return f"assets/{namespace}/models/item/{item_path}.json", direct

        definition_path = f"assets/{namespace}/items/{item_path}.json"
        definition = self._json(definition_path)
        model_location = self._first_model(definition.get("model", definition))
        model_path = self._location(
            model_location or f"{namespace}:item/{item_path}", namespace, "models", ".json"
        )
        textures: dict[str, str] = {}
        visited = set()
        current = model_path
        for _depth in range(20):
            key = self._resource_key(current)
            if not current or key in visited:
                break
            visited.add(key)
            model = self._json(current)
            if not model:
                break
            for name, value in model.get("textures", {}).items() if isinstance(model.get("textures"), dict) else []:
                textures.setdefault(str(name), str(value))
            parent = model.get("parent", "")
            if not isinstance(parent, str) or not parent or parent.startswith("builtin/"):
                break
            current = self._location(parent, namespace, "models", ".json")

        texture = textures.get("layer0") or textures.get("all") or textures.get("particle")
        if not texture and textures:
            texture = next(iter(textures.values()))
        for _depth in range(12):
            if not isinstance(texture, str) or not texture.startswith("#"):
                break
            texture = textures.get(texture[1:], "")
        texture_path = self._location(texture, namespace, "textures", ".png") if texture else ""
        if self._resource_key(texture_path) not in self.resources:
            texture_path = ""
        return model_path, texture_path

    def _resolve_assets(self) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        for item in self.items.values():
            if ":" not in item.item_id:
                continue
            item.model_path, item.texture_path = self._resolve_texture(item.item_id)
            if item.texture_path:
                item.render_status = "texture"
            elif self._resource_key(item.model_path) in self.resources:
                item.render_status = "model_fallback"

    def icon_for(self, item_id: str) -> str:
        item = self.items.get(item_id)
        if item is None or not item.texture_path:
            return ""
        if item.icon_path and os.path.isfile(item.icon_path):
            return item.icon_path
        ref = self.resources.get(self._resource_key(item.texture_path))
        if ref is None:
            return ""
        digest = hashlib.sha1(
            f"{item_id}|{ref.source}|{ref.entry}|{ref.modified}".encode("utf-8")
        ).hexdigest()[:16]
        target = os.path.join(self.cache_dir, f"{digest}.png")
        if not os.path.isfile(target):
            try:
                if ref.entry:
                    with open(target, "wb") as handle:
                        handle.write(ref.read())
                else:
                    shutil.copyfile(ref.source, target)
            except OSError:
                return ""
        item.icon_path = target
        return target

    def summary(self) -> dict:
        resolved = sum(1 for item in self.items.values() if item.texture_path)
        model_only = sum(1 for item in self.items.values() if item.render_status == "model_fallback")
        return {
            "items": len(self.items),
            "icons": resolved,
            "model_fallbacks": model_only,
            "resources": len(self.resources),
        }
