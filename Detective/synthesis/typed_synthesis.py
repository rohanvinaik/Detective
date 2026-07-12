"""Typed value synthesis — resolve a type annotation into a constructible test value.

Single source of truth for parameter filling: primitives → literal defaults,
containers → empty (or one populated element for dataclass elements), dataclasses
→ minimal construction of their required fields. Falls back to name heuristics
when type info is absent.

Clean-room port of LintGate's typed_synthesis. Drops the reference's LintGate
coupling: no hardcoded ``_KNOWN_MODULES`` table (dataclasses resolve from the
source module only), no domain-specific name heuristics, and no legacy
``ast.dump``-string parsing path (annotations are raw strings via ast.unparse).
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import MISSING, dataclass
from dataclasses import fields as dc_fields
from dataclasses import is_dataclass
from typing import Any

_PRIMITIVE_DEFAULTS: dict[str, str] = {
    "str": '""',
    "int": "0",
    "float": "0.0",
    "bool": "False",
    "bytes": 'b""',
}


@dataclass(frozen=True)
class SynthesizedValue:
    """A synthesized test input value with the imports its code needs."""

    code: str
    imports: tuple[str, ...] = ()
    is_placeholder: bool = False
    type_name: str = ""


def synthesize_value(annotation: str, param_name: str = "", module_path: str = "") -> SynthesizedValue:
    """Synthesize a valid test value from a type annotation string.

    ``annotation`` is a raw Python annotation (e.g. ``"list[Foo]"``). Returns a
    placeholder (via name heuristics) when the type is absent, ``Any``, or
    unresolvable.
    """
    if not annotation:
        return _fallback(param_name)

    base, args = _parse_annotation(annotation)
    if not base:
        return _fallback(param_name)

    if base in ("None", "NoneType"):
        return SynthesizedValue("None", type_name="None")

    if base in _PRIMITIVE_DEFAULTS:
        code = _heuristic_value(param_name) if base == "str" and param_name else _PRIMITIVE_DEFAULTS[base]
        return SynthesizedValue(code, type_name=base)

    if base in ("list", "List"):
        if args:
            inner = synthesize_value(args[0], "", module_path)
            if not inner.is_placeholder and inner.type_name not in _PRIMITIVE_DEFAULTS:
                return SynthesizedValue(f"[{inner.code}]", inner.imports, False, f"list[{inner.type_name}]")
        return SynthesizedValue("[]", type_name="list")

    if base in ("dict", "Dict"):
        return SynthesizedValue("{}", type_name="dict")

    if base in ("set", "Set"):
        return SynthesizedValue("set()", type_name="set")

    if base in ("tuple", "Tuple"):
        return SynthesizedValue("()", type_name="tuple")

    if base == "Optional":
        return synthesize_value(args[0], param_name, module_path) if args else SynthesizedValue("None", type_name="Optional")

    if base == "Any":
        return _fallback(param_name)

    cls = _resolve_dataclass(base, module_path)
    if cls is not None:
        code, imports = _dataclass_construction(cls)
        return SynthesizedValue(code, imports, False, base)

    return _fallback(param_name)


# ── Annotation parsing ────────────────────────────────────────────


def _parse_annotation(hint: str) -> tuple[str, list[str]]:
    """Parse a raw annotation string into ``(base_type, [type_args])``."""
    try:
        node = ast.parse(hint, mode="eval").body
    except SyntaxError:
        return ("", [])
    return _extract(node)


def _extract(node: ast.expr) -> tuple[str, list[str]]:
    if isinstance(node, ast.Constant) and node.value is None:
        return ("None", [])
    if isinstance(node, ast.Name):
        return (node.id, [])
    if isinstance(node, ast.Attribute):
        return (node.attr, [])
    if isinstance(node, ast.Subscript):
        base = _extract(node.value)[0]
        slice_node = node.slice
        if isinstance(slice_node, ast.Tuple):
            args = [_extract(e)[0] for e in slice_node.elts]
        else:
            args = [_extract(slice_node)[0]]
        return (base, args)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _extract(node.left), _extract(node.right)
        return right if left[0] == "None" else left
    return ("", [])


# ── Dataclass introspection ───────────────────────────────────────


def _resolve_dataclass(type_name: str, module_path: str) -> Any:
    """Resolve ``type_name`` to a dataclass defined in the source module."""
    if not module_path:
        return None
    try:
        mod = importlib.import_module(module_path)
    except (ImportError, ModuleNotFoundError):
        return None
    cls = getattr(mod, type_name, None)
    return cls if cls is not None and is_dataclass(cls) else None


def _dataclass_construction(cls: type) -> tuple[str, tuple[str, ...]]:
    """Emit ``Cls(field=value, ...)`` filling only the required (no-default) fields."""
    args = [
        f"{f.name}={_heuristic_value(f.name, _type_str(f.type))}"
        for f in dc_fields(cls)
        if f.default is MISSING and f.default_factory is MISSING
    ]
    code = f"{cls.__name__}({', '.join(args)})"
    return code, (f"from {cls.__module__} import {cls.__name__}",)


def _type_str(type_hint: Any) -> str:
    if isinstance(type_hint, str):
        return type_hint
    if hasattr(type_hint, "__name__"):
        return type_hint.__name__
    if hasattr(type_hint, "__origin__"):
        return getattr(type_hint.__origin__, "__name__", "")
    return ""


# ── Value heuristics ──────────────────────────────────────────────


def _heuristic_value(name: str, type_str: str = "str") -> str:
    """A plausible literal for a field, by name first then type."""
    low = name.lower()
    if "name" in low or "key" in low:
        return '"test"'
    if "path" in low or "file" in low:
        return '"test.py"'
    if "message" in low or "msg" in low:
        return '"test message"'
    if type_str in ("int", "integer"):
        return "1"
    if type_str == "float":
        return "1.0"
    if type_str == "bool":
        return "False"
    return '"test"'


def _fallback(param_name: str) -> SynthesizedValue:
    """Name-heuristic placeholder when type info is unavailable."""
    low = param_name.lower() if param_name else ""
    if "path" in low or "file" in low or "dir" in low:
        return SynthesizedValue('"test.py"', is_placeholder=True, type_name="str")
    if "name" in low or "key" in low:
        return SynthesizedValue('"test"', is_placeholder=True, type_name="str")
    if "count" in low or "num" in low or "size" in low:
        return SynthesizedValue("0", is_placeholder=True, type_name="int")
    if "flag" in low or "enable" in low or "is_" in low:
        return SynthesizedValue("False", is_placeholder=True, type_name="bool")
    return SynthesizedValue("None", is_placeholder=True, type_name="unknown")
