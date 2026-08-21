"""Read-only, model-agnostic query tools over a scanned modpack."""

from __future__ import annotations

import json
import re


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


class QuestToolbox:
    """Small structured queries used by generation today and tool calling later."""

    def __init__(self, all_items=None, recipe_inputs=None, documents=None):
        self.all_items = all_items or {}
        self.recipe_inputs = recipe_inputs or {}
        self.documents = list(documents or [])

    def search_items(self, namespace="", query="", limit=30) -> list[dict]:
        namespace = str(namespace or "").strip().lower()
        needle = _normalized(query)
        limit = max(1, min(int(limit), 100))
        matches = []
        for candidate_ns, items in self.all_items.items():
            if namespace and candidate_ns.lower() != namespace:
                continue
            if not isinstance(items, dict):
                continue
            for item_id, display_name in items.items():
                haystacks = (_normalized(item_id), _normalized(display_name))
                if needle and not any(needle in value for value in haystacks):
                    continue
                exact = needle and any(needle == value for value in haystacks)
                prefix = needle and any(value.startswith(needle) for value in haystacks)
                matches.append((not exact, not prefix, str(item_id), str(display_name)))
        matches.sort()
        return [
            {"item_id": item_id, "name": name, "namespace": item_id.split(":", 1)[0]}
            for _, _, item_id, name in matches[:limit]
        ]

    def resolve_namespaces(self, requested) -> list[str]:
        available = sorted(str(value) for value in self.all_items)
        resolved = []
        for raw in requested or []:
            namespace = str(raw or "").strip()
            if not namespace:
                continue
            if namespace in self.all_items:
                resolved.append(namespace)
                continue
            needle = _normalized(namespace)
            match = next(
                (
                    candidate for candidate in available
                    if len(needle) >= 3 and (
                        needle in _normalized(candidate)
                        or _normalized(candidate) in needle
                    )
                ),
                None,
            )
            if match:
                resolved.append(match)
        return list(dict.fromkeys(resolved))

    def build_item_catalog(self, namespaces, limit_per_namespace=100) -> str:
        """Return a bounded chapter catalog instead of the entire modpack inventory."""
        lines = ["=== 按需查询到的本章物品 ==="]
        for namespace in self.resolve_namespaces(namespaces):
            items = self.search_items(namespace, limit=limit_per_namespace)
            if not items:
                continue
            recipe_outputs = set(self.recipe_inputs)
            items.sort(key=lambda item: (item["item_id"] not in recipe_outputs, item["item_id"]))
            lines.append(f"{namespace} ({len(items)}):")
            for start in range(0, len(items), 12):
                chunk = items[start:start + 12]
                lines.append("  " + ", ".join(
                    f"{item['item_id']} ({item['name']})" for item in chunk
                ))
        return "\n".join(lines) if len(lines) > 1 else ""

    def get_item(self, item_id: str) -> dict | None:
        item_id = str(item_id or "").strip()
        if ":" not in item_id:
            return None
        namespace = item_id.split(":", 1)[0]
        items = self.all_items.get(namespace, {})
        if not isinstance(items, dict) or item_id not in items:
            return None
        return {"item_id": item_id, "name": str(items[item_id]), "namespace": namespace}

    def get_recipe(self, item_id: str, depth=1) -> dict:
        item_id = str(item_id or "").strip()
        depth = max(0, min(int(depth), 4))

        def expand(target, remaining, visiting):
            inputs = self.recipe_inputs.get(target, [])
            result = {"output": target, "inputs": list(inputs) if isinstance(inputs, list) else []}
            if remaining and target not in visiting:
                next_visiting = set(visiting)
                next_visiting.add(target)
                result["prerequisites"] = [
                    expand(value, remaining - 1, next_visiting)
                    for value in result["inputs"]
                    if value in self.recipe_inputs
                ][:12]
            return result

        return expand(item_id, depth, set())

    def validate_ids(self, item_ids) -> list[dict]:
        results = []
        for raw in item_ids or []:
            item_id = str(raw or "").strip()
            if ":" not in item_id:
                results.append({"item_id": item_id, "status": "invalid"})
                continue
            namespace = item_id.split(":", 1)[0]
            items = self.all_items.get(namespace)
            if isinstance(items, dict) and item_id in items:
                status = "valid"
            elif namespace in self.all_items:
                status = "unknown"
            else:
                status = "unverified"
            results.append({"item_id": item_id, "status": status})
        return results

    def tool_specs(self) -> list[dict]:
        """Return OpenAI-compatible read-only tool schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_items",
                    "description": "Search real item IDs in the current modpack index.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string"},
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 30},
                        },
                        "required": ["namespace", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_item",
                    "description": "Get one exact item from the current modpack index.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string"}},
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recipe",
                    "description": "Get recipe inputs and a bounded prerequisite chain.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string"},
                            "depth": {"type": "integer", "minimum": 0, "maximum": 3},
                        },
                        "required": ["item_id"],
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        """Execute one allow-listed read-only query and return compact JSON."""
        arguments = arguments if isinstance(arguments, dict) else {}
        if name == "search_items":
            value = self.search_items(
                arguments.get("namespace", ""),
                arguments.get("query", ""),
                min(int(arguments.get("limit", 20)), 30),
            )
        elif name == "get_item":
            value = self.get_item(arguments.get("item_id", ""))
        elif name == "get_recipe":
            value = self.get_recipe(
                arguments.get("item_id", ""),
                arguments.get("depth", 1),
            )
        else:
            value = {"error": f"Unknown read-only tool: {name}"}
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
