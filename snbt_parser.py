"""Minimal SNBT reader/writer for FTB Quests quest files.

The FTB Quests on-disk format is a relaxed variant of Minecraft's SNBT:
unquoted keys, optional commas, and numeric suffixes (d/L/b). This module
parses the subset produced by AutoFTBQ and the example quest books, and
serializes plain Python values back into the same relaxed syntax.
"""

from __future__ import annotations

import re
from typing import Any


class SNBTParseError(ValueError):
    pass


class _SNBTFloat(float):
    """Float that renders with a trailing ``d``."""

    def __repr__(self) -> str:
        text = super().__repr__()
        if "." not in text:
            text += ".0"
        return f"{text}d"


class _SNBTLong(int):
    def __repr__(self) -> str:
        return f"{super().__repr__()}L"


class _SNBTByte(int):
    def __repr__(self) -> str:
        return f"{super().__repr__()}b"


class _SNBTShort(int):
    def __repr__(self) -> str:
        return f"{super().__repr__()}s"


class _SNBTTypedArray(list):
    """List-like SNBT typed array that preserves its on-disk element kind."""

    def __init__(self, kind: str, values=()):
        super().__init__(values)
        self.kind = str(kind).upper()


def _parse_string(text: str, i: int) -> tuple[str, int]:
    """Parse a double-quoted string starting at ``text[i]``."""
    assert text[i] == '"'
    i += 1
    out: list[str] = []
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            if i + 1 >= len(text):
                raise SNBTParseError("unterminated escape sequence")
            nxt = text[i + 1]
            if nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            else:
                out.append(nxt)
            i += 2
        elif ch == '"':
            return "".join(out), i + 1
        else:
            out.append(ch)
            i += 1
    raise SNBTParseError("unterminated string literal")


_NUMBER_RE = re.compile(
    r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?([dDfFbBsSlL])?$"
)


def parse_snbt(text: str) -> Any:
    """Parse SNBT text into plain Python values.

    Numbers with ``d``/``f`` suffixes become floats, ``L``/``b``/``s`` become
    ints wrapped so they re-serialize with their original suffix.
    """

    pos = 0

    def skip_ws() -> None:
        nonlocal pos
        while pos < len(text) and text[pos] in " \t\r\n":
            pos += 1

    def parse_atom() -> Any:
        nonlocal pos
        skip_ws()
        start = pos
        while pos < len(text) and text[pos] not in ",]} \t\r\n":
            pos += 1
        token = text[start:pos]
        if not token:
            raise SNBTParseError(f"unexpected character {text[pos:pos + 1]!r}")
        lowered = token.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in ("null",):
            return None
        match = _NUMBER_RE.match(token)
        if match:
            suffix = (match.group(1) or "").lower()
            if "." in token or "e" in lowered or suffix in ("d", "f"):
                value = float(token.rstrip("dDfF"))
                return _SNBTFloat(value) if suffix in ("d", "f") else value
            value = int(token.rstrip("lLsSbB"))
            if suffix == "l":
                return _SNBTLong(value)
            if suffix == "b":
                return _SNBTByte(value)
            if suffix == "s":
                return _SNBTShort(value)
            return value
        # Unquoted bare string (rare, but appears in some files).
        return token

    def parse_key() -> str:
        nonlocal pos
        skip_ws()
        if pos < len(text) and text[pos] == '"':
            key, new_pos = _parse_string(text, pos)
            pos = new_pos
            return key
        start = pos
        while pos < len(text) and text[pos] not in ": \t\r\n":
            pos += 1
        key = text[start:pos]
        if not key:
            raise SNBTParseError("empty key in compound")
        return key

    def parse_dict() -> dict[str, Any]:
        nonlocal pos
        pos += 1  # consume {
        result: dict[str, Any] = {}
        while True:
            skip_ws()
            if pos >= len(text):
                raise SNBTParseError("unterminated compound, missing }")
            if text[pos] == "}":
                pos += 1
                return result
            key = parse_key()
            skip_ws()
            if pos < len(text) and text[pos] == ":":
                pos += 1
            result[key] = parse_value()
            skip_ws()
            if pos < len(text) and text[pos] == ",":
                pos += 1

    def parse_list() -> list[Any]:
        nonlocal pos
        pos += 1  # consume [
        result: list[Any] = []
        skip_ws()
        # Typed arrays such as [I; -800846297 -1505998786]
        if (
            pos + 1 < len(text)
            and text[pos] in "IBLFS"
            and text[pos + 1] == ";"
        ):
            array_kind = text[pos]
            pos += 2
            typed_result = _SNBTTypedArray(array_kind)
            while True:
                skip_ws()
                if pos >= len(text):
                    raise SNBTParseError("unterminated typed array, missing ]")
                if text[pos] == "]":
                    pos += 1
                    return typed_result
                typed_result.append(parse_atom())
                skip_ws()
                if pos < len(text) and text[pos] == ",":
                    pos += 1
        while True:
            skip_ws()
            if pos >= len(text):
                raise SNBTParseError("unterminated list, missing ]")
            if text[pos] == "]":
                pos += 1
                return result
            result.append(parse_value())
            skip_ws()
            if pos < len(text) and text[pos] == ",":
                pos += 1

    def parse_value() -> Any:
        nonlocal pos
        skip_ws()
        if pos >= len(text):
            raise SNBTParseError("unexpected end of input")
        ch = text[pos]
        if ch == "{":
            return parse_dict()
        if ch == "[":
            return parse_list()
        if ch == '"':
            value, new_pos = _parse_string(text, pos)
            pos = new_pos
            return value
        return parse_atom()

    value = parse_value()
    skip_ws()
    if pos != len(text):
        raise SNBTParseError(f"trailing content at offset {pos}")
    return value


def _snbt_value(value: Any, indent: int, level: int) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (_SNBTFloat, _SNBTLong, _SNBTByte, _SNBTShort)):
        return repr(value)
    if isinstance(value, float):
        text = repr(value)
        if "." not in text:
            text += ".0"
        return f"{text}d"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    if isinstance(value, _SNBTTypedArray):
        return _snbt_typed_array(value, indent, level)
    if isinstance(value, list):
        return _snbt_list(value, indent, level)
    if isinstance(value, dict):
        return _snbt_dict(value, indent, level)
    return str(value)


def _snbt_list(values: list[Any], indent: int, level: int) -> str:
    if not values:
        return "[]"
    pad = " " * indent * level
    inner = " " * indent * (level + 1)
    items = [f"{inner}{_snbt_value(item, indent, level + 1)}" for item in values]
    return "[\n" + "\n".join(items) + "\n" + pad + "]"


def _snbt_typed_array(values: _SNBTTypedArray, indent: int, level: int) -> str:
    if not values:
        return f"[{values.kind};]"
    pad = " " * indent * level
    inner = " " * indent * (level + 1)
    items = [f"{inner}{_snbt_value(item, indent, level + 1)}" for item in values]
    return f"[{values.kind};\n" + "\n".join(items) + "\n" + pad + "]"


_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9._+-]+$")


def _snbt_key(key: Any) -> str:
    text = str(key)
    if _BARE_KEY_RE.fullmatch(text):
        return text
    return _snbt_value(text, 0, 0)


def _snbt_dict(values: dict[str, Any], indent: int, level: int) -> str:
    if not values:
        return "{}"
    pad = " " * indent * level
    inner = " " * indent * (level + 1)
    lines = [
        f"{inner}{_snbt_key(key)}: {_snbt_value(value, indent, level + 1)}"
        for key, value in values.items()
    ]
    return "{\n" + "\n".join(lines) + "\n" + pad + "}"


def to_snbt(value: Any, indent: int = 4) -> str:
    """Serialize Python values into the relaxed SNBT syntax."""
    if isinstance(value, dict):
        return _snbt_dict(value, indent, 0)
    if isinstance(value, list):
        return _snbt_list(value, indent, 0)
    return _snbt_value(value, indent, 0)
