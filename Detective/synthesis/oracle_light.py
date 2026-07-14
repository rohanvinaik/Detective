"""Oracle-light executable properties from mutation survivors.

Transforms a surviving mutant into an executable *relational* assertion. SWAP,
BOUNDARY, TYPE, and STATE(return_none) are oracle-light — they produce valid
assertions with no expected-output value. VALUE and STATE(remove_assign) need an
oracle and are flagged ``needs_oracle=True``.

Clean-room port of LintGate's oracle_light core (dispatch + the six category
generators + extractors). The ``to_dict`` field-enumeration path and round-trip
pair detection are deferred as follow-on features.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from .typed_synthesis import _resolve_dataclass, synthesize_value


@dataclass
class ExecutableProperty:
    """A structured executable test property derived from a mutation survivor."""

    category: str
    inputs: dict[str, Any]
    setup_code: str  # no indent — the caller adds it
    assertion_code: str  # no indent, multi-line OK
    preconditions: list[str]
    confidence: float
    source_lenses: list[str] = field(default_factory=list)
    needs_oracle: bool = False
    function_key: str = ""
    mutant_id: str = ""
    # For a golden-capture VALUE property with an idiomatic ``==`` assertion: the
    # ``(args_tuple_repr, expected_repr)`` pair, so the renderer can fold 2+ of them into
    # one ``@pytest.mark.parametrize`` test. None → render as an individual test.
    golden_case: tuple[str, str] | None = None


def generate_executable_property(
    survivor: dict[str, Any],
    func_key: str,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None,
    call_site_inputs: list[dict] | None = None,
) -> ExecutableProperty:
    """Generate an executable property from a mutation survivor record."""
    generator = _GENERATORS.get(survivor.get("category", ""), _generic_property)
    prop = generator(survivor, func_key, func_node, call_site_inputs)
    prop.function_key = func_key
    prop.mutant_id = survivor.get("mutant_id", "")
    return prop


# ── Helpers ───────────────────────────────────────────────────────


def _func_info(
    func_key: str, func_node: ast.FunctionDef | ast.AsyncFunctionDef | None
) -> tuple[str, str, list[str]]:
    """Extract ``(module_path, func_name, params)``."""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    params = [a.arg for a in func_node.args.args if a.arg not in ("self", "cls")] if func_node else []
    return mod, fname, params


def _bare_name(name: str) -> str:
    return name.split(".")[-1]


def _import_line(module_path: str, func_name: str) -> str:
    if not module_path:
        return ""
    top = func_name.split(".")[0]
    mod = module_path.replace("/", ".").replace("\\", ".")
    if mod.endswith(".py"):
        mod = mod[:-3]
    return f"from {mod} import {top}"


def _parse_diff_changes(diff: str) -> list[tuple[str, str]]:
    """Extract ``(original, mutated)`` changed-line pairs from a diff summary."""
    if not diff or "\n+ " not in diff:
        return []
    idx = diff.index("\n+ ")
    original, mutated = diff[2:idx], diff[idx + 3 :]
    return [
        (o.strip(), m.strip())
        for o, m in zip(original.split("\n"), mutated.split("\n"), strict=False)
        if o.strip() != m.strip()
    ]


# ── Category generators ───────────────────────────────────────────


def _swap_property(_survivor, func_key, func_node, call_site_inputs) -> ExecutableProperty:
    """SWAP: ``f(a, b) != f(b, a)`` — sound when order provably matters."""
    mod, fname, params = _func_info(func_key, func_node)
    setup = _import_line(mod, fname)

    if len(params) < 2:
        return _skip("SWAP", setup, f"# SWAP survived but {fname} has <2 params", 0.3)

    typed_skip = _swap_type_skip(func_node, setup)
    if typed_skip is not None:
        return typed_skip

    a_val, b_val = _distinct_values(call_site_inputs)
    assertion = (
        f"result_ab = {fname}({a_val}, {b_val})\n"
        f"result_ba = {fname}({b_val}, {a_val})\n"
        f'assert result_ab != result_ba, "SWAP: parameter order should matter"'
    )
    return ExecutableProperty(
        category="SWAP",
        inputs={params[0]: a_val, params[1]: b_val},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=[f"{params[0]} != {params[1]}", "non-commutative"],
        confidence=0.75 if call_site_inputs else 0.6,
        source_lenses=["mutation"] + (["call_sites"] if call_site_inputs else []),
        needs_oracle=False,
    )


def _swap_type_skip(func_node, setup: str) -> ExecutableProperty | None:
    """Skip SWAP when the first two params have provably different annotated types."""
    if func_node is None:
        return None
    args = [a for a in func_node.args.args if a.arg not in ("self", "cls")]
    if len(args) < 2 or args[0].annotation is None or args[1].annotation is None:
        return None
    ann_a, ann_b = args[0].annotation, args[1].annotation
    if ast.dump(ann_a) == ast.dump(ann_b):
        return None
    name_a = ann_a.id if isinstance(ann_a, ast.Name) else ast.dump(ann_a)
    name_b = ann_b.id if isinstance(ann_b, ast.Name) else ast.dump(ann_b)
    return _skip("SWAP", setup, f"# SWAP skipped: params have different types ({name_a} vs {name_b})", 0.1)


def _boundary_property(survivor, func_key, func_node, call_site_inputs) -> ExecutableProperty:
    """BOUNDARY: behavior differs across the actual predicate boundary pair."""
    mod, fname, params = _func_info(func_key, func_node)
    setup = _import_line(mod, fname)

    info = _extract_boundary_info(survivor.get("diff_summary", ""))
    if info is None:
        return _skip("BOUNDARY", setup, "# BOUNDARY survived but boundary value not extractable", 0.3)

    bval, bvar, comp = info["boundary_value"], info.get("variable"), info.get("comparator", "")
    step = 1 if isinstance(bval, int) else 0.1
    other_vals = _other_param_values(params, bvar, call_site_inputs)
    call_at = _build_call(fname, params, bvar, bval, other_vals)
    call_before = _build_call(fname, params, bvar, bval - step, other_vals)
    has_unknowns = "..." in call_at
    label = f"{bvar}=" if bvar else ""

    assertion = (
        f"result_at = {call_at}\n"
        f"result_before = {call_before}\n"
        f'assert result_at != result_before, "BOUNDARY at {label}{bval}: {comp} should discriminate"'
    )
    return ExecutableProperty(
        category="BOUNDARY",
        inputs={bvar or (params[0] if params else "x"): bval},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=[f"boundary at {label}{bval} ({comp})"],
        confidence=0.85 if not has_unknowns else 0.5,
        source_lenses=["mutation", "diff_analysis"],
        needs_oracle=has_unknowns,
    )


def _type_property(survivor, func_key, func_node, _call_site_inputs) -> ExecutableProperty:
    """TYPE: a wrong type should be rejected (raise)."""
    mod, fname, _ = _func_info(func_key, func_node)
    imp = _import_line(mod, fname)
    setup = f"{imp}\nimport pytest" if imp else "import pytest"
    expected_type = _extract_isinstance_type(survivor.get("diff_summary", ""))

    if not expected_type:
        assertion = (
            "with pytest.raises((TypeError, ValueError)):\n"
            f"    {fname}(None)  # TODO: use appropriate invalid type"
        )
        return ExecutableProperty(
            category="TYPE",
            inputs={},
            setup_code=setup,
            assertion_code=assertion,
            preconditions=["expected type unknown"],
            confidence=0.4,
            source_lenses=["mutation"],
            needs_oracle=True,
        )

    invalid = _INVALID_FOR_TYPE.get(expected_type, "None")
    assertion = (
        f"# isinstance checks {expected_type} — wrong type should be rejected\n"
        "with pytest.raises((TypeError, ValueError)):\n"
        f"    {fname}({invalid})"
    )
    return ExecutableProperty(
        category="TYPE",
        inputs={"invalid_type": invalid},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=[f"isinstance checks {expected_type}"],
        confidence=0.7,
        source_lenses=["mutation", "diff_analysis"],
        needs_oracle=False,
    )


def _state_property(survivor, func_key, func_node, call_site_inputs) -> ExecutableProperty:
    """STATE: a return value or set attribute must be verified."""
    mod, fname, params = _func_info(func_key, func_node)
    setup = _import_line(mod, fname)
    desc = survivor.get("description", "")
    diff = survivor.get("diff_summary", "")

    if "return_none" in desc:
        call_args = _call_args_from_sites(call_site_inputs) or "..."
        assertion = (
            f"result = {fname}({call_args})\n"
            'assert result is not None, "STATE: return value should not be None"'
        )
        return ExecutableProperty(
            category="STATE",
            inputs={},
            setup_code=setup,
            assertion_code=assertion,
            preconditions=["function returns a meaningful value"],
            confidence=0.7,
            source_lenses=["mutation"],
            needs_oracle=False,
        )

    attr = _extract_self_attr(diff)
    rhs_info = _extract_assign_rhs(diff, params) if attr else None
    if attr and rhs_info:
        class_name = fname.split(".")[0] if "." in fname else None
        if class_name:
            call_args = _call_args_from_sites(call_site_inputs) or "..."
            assertion = (
                f"obj = {class_name}({call_args})\n"
                f"obj.{_bare_name(fname)}({call_args})\n"
                f"assert obj.{attr} == {rhs_info[1]}"
            )
            return ExecutableProperty(
                category="STATE",
                inputs={},
                setup_code=_import_line(mod, class_name),
                assertion_code=assertion,
                preconditions=[f"construct {class_name}"],
                confidence=0.65,
                source_lenses=["mutation", "diff_analysis", "state_fast_path"],
                needs_oracle=False,
            )

    hint = f"self.{attr}" if attr else "attribute"
    assertion = (
        f"# STATE: {hint} assignment removed — verify it's set after call\n"
        "# obj = ClassName(...)\n"
        f"# obj.{fname}(...)\n"
        f"# assert obj.{attr or 'ATTR'} == EXPECTED  # FILL"
    )
    return ExecutableProperty(
        category="STATE",
        inputs={},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=["construct object", f"verify {hint}"],
        confidence=0.4 if attr else 0.2,
        source_lenses=["mutation"] + (["diff_analysis"] if attr else []),
        needs_oracle=True,
    )


def _value_property(_survivor, func_key, func_node, call_site_inputs) -> ExecutableProperty:
    """VALUE: exact output needed — oracle-dependent."""
    mod, fname, _ = _func_info(func_key, func_node)
    setup = _import_line(mod, fname)
    call_args = _call_args_from_sites(call_site_inputs) or "..."
    assertion = f"result = {fname}({call_args})\nassert result == ...  # FILL: expected value"
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=["exact expected value must be determined"],
        confidence=0.3,
        source_lenses=["mutation"] + (["call_sites"] if call_site_inputs else []),
        needs_oracle=True,
    )


def _stmt_property(_survivor, func_key, func_node, call_site_inputs) -> ExecutableProperty:
    """STMT: a side-effecting statement was deleted and no test noticed — either the
    statement is dead code (equivalent, remove it) or its side effect is unobserved.
    Oracle-required: the test must observe the effect; we never fabricate what it is."""
    mod, fname, _ = _func_info(func_key, func_node)
    setup = _import_line(mod, fname)
    call_args = _call_args_from_sites(call_site_inputs) or "..."
    assertion = (
        f"# STMT: a side-effecting statement in {fname} was deleted and no test noticed.\n"
        "# Either it is dead code (remove it) or its side effect is unobserved.\n"
        f"# result = {fname}({call_args})\n"
        "# assert <observable effect of that statement>  # FILL: observe the side effect"
    )
    return ExecutableProperty(
        category="STMT",
        inputs={},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=["observe the deleted statement's side effect, or confirm dead code"],
        confidence=0.3,
        source_lenses=["mutation"],
        needs_oracle=True,
    )


def _generic_property(survivor, _func_key, _func_node, _call_site_inputs) -> ExecutableProperty:
    cat = survivor.get("category", "UNKNOWN")
    return ExecutableProperty(
        category=cat,
        inputs={},
        setup_code="",
        assertion_code=f"# {cat} mutation survived — manual investigation needed",
        preconditions=[],
        confidence=0.2,
        source_lenses=["mutation"],
        needs_oracle=True,
    )


_GENERATORS = {
    "SWAP": _swap_property,
    "BOUNDARY": _boundary_property,
    "TYPE": _type_property,
    "STATE": _state_property,
    "VALUE": _value_property,
    "STMT": _stmt_property,
}


def _skip(category: str, setup: str, message: str, confidence: float) -> ExecutableProperty:
    """A no-op property emitted when the category can't produce a sound assertion."""
    return ExecutableProperty(
        category=category,
        inputs={},
        setup_code=setup,
        assertion_code=message,
        preconditions=[],
        confidence=confidence,
        source_lenses=["mutation"],
        needs_oracle=True,
    )


# ── Diff extractors ───────────────────────────────────────────────


def _extract_boundary_info(diff: str) -> dict[str, Any] | None:
    for orig, _ in _parse_diff_changes(diff):
        m = re.search(r"(\w+)\s*([<>]=?)\s*(\d+(?:\.\d+)?)", orig)
        if m:
            val = m.group(3)
            return {
                "variable": m.group(1),
                "comparator": m.group(2),
                "boundary_value": float(val) if "." in val else int(val),
            }
    return None


def _extract_isinstance_type(diff: str) -> str | None:
    for orig, _ in _parse_diff_changes(diff):
        m = re.search(r"isinstance\(\s*\w+\s*,\s*(\w+(?:\.\w+)*)", orig)
        if m:
            return m.group(1)
    return None


def _extract_self_attr(diff: str) -> str | None:
    for orig, _ in _parse_diff_changes(diff):
        m = re.search(r"self\.(\w+)\s*=", orig)
        if m:
            return m.group(1)
    return None


def _extract_assign_rhs(diff: str, params: list[str]) -> tuple[str, str] | None:
    """Extract a ``self.attr = rhs`` RHS when it's a param or a literal."""
    for orig, _ in _parse_diff_changes(diff):
        m = re.match(r"self\.\w+\s*=\s*(.+)$", orig.strip())
        if not m:
            continue
        rhs = m.group(1).strip()
        if rhs in params:
            return ("param", rhs)
        if re.fullmatch(r"-?\d+(?:\.\d+)?", rhs):
            return ("literal", rhs)
        if re.fullmatch(r"""(['"]).*?\1""", rhs):
            return ("literal", rhs)
        if rhs in ("True", "False", "None"):
            return ("literal", rhs)
    return None


# ── Input helpers ─────────────────────────────────────────────────

_INVALID_FOR_TYPE: dict[str, str] = {
    "str": "42",
    "int": "'not_int'",
    "float": "'not_float'",
    "bool": "42",
    "list": "42",
    "dict": "42",
    "tuple": "42",
}


def _distinct_values(sites: list[dict] | None) -> tuple[str, str]:
    for s in sites or []:
        args = s.get("positional_args") or s.get("args") or []
        if len(args) >= 2 and str(args[0]) != str(args[1]):
            return str(args[0]), str(args[1])
    return "1", "2"


def _call_args_from_sites(sites: list[dict] | None) -> str:
    for s in sites or []:
        m = re.search(r"\(([^)]+)\)", s.get("context", ""))
        if m:
            return m.group(1)
    return ""


def _other_param_values(
    params: list[str], boundary_var: str | None, sites: list[dict] | None
) -> dict[str, str]:
    vals: dict[str, str] = {}
    for s in sites or []:
        args = s.get("positional_args") or s.get("args") or []
        for i, p in enumerate(params):
            if p != boundary_var and i < len(args):
                vals[p] = str(args[i])
    return vals


def _build_call(
    fname: str, params: list[str], boundary_var: str | None, boundary_val: Any, other_vals: dict[str, str]
) -> str:
    if not params:
        return f"{fname}({boundary_val})"
    args = [str(boundary_val) if p == boundary_var else other_vals.get(p, "...") for p in params]
    return f"{fname}({', '.join(args)})"


# ── SWAP emission gate ────────────────────────────────────────────

# Parameter-name pairs whose order is inherently meaningful.
_NON_COMMUTATIVE_PAIRS = frozenset(
    {
        frozenset({"numerator", "denominator"}),
        frozenset({"start", "end"}),
        frozenset({"start", "stop"}),
        frozenset({"lo", "hi"}),
        frozenset({"minuend", "subtrahend"}),
        frozenset({"base", "exponent"}),
    }
)


def should_emit_swap_test(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef | None, survivors: list[dict] | None = None
) -> bool:
    """Whether a cross-parameter swap test is warranted.

    Emits only when a real SWAP survivor exists, the first two params are a
    known non-commutative pair, or they share a suffix with distinct prefixes
    (e.g. ``static_level`` vs ``empirical_level``). Never for generic "2+ params".
    """
    if survivors and any(s.get("category") == "SWAP" for s in survivors):
        return True
    if func_node is None:
        return False
    params = [a.arg for a in func_node.args.args if a.arg not in ("self", "cls")]
    if len(params) < 2:
        return False
    if frozenset(params[:2]) in _NON_COMMUTATIVE_PAIRS:
        return True
    return _params_have_distinct_prefixes(params[0], params[1])


def _params_have_distinct_prefixes(a: str, b: str) -> bool:
    """True when two names share a trailing segment but differ in the first."""
    parts_a, parts_b = a.split("_"), b.split("_")
    if len(parts_a) < 2 or len(parts_b) < 2:
        return False
    return parts_a[-1] == parts_b[-1] and parts_a[0] != parts_b[0]


# ── Round-trip pair detection ─────────────────────────────────────


def detect_round_trip_pairs(source_file: str) -> list[tuple[str, str, str]]:
    """Detect serialize/deserialize pairs in a file.

    Returns ``(class_name, serialize_method, deserialize_func)`` tuples: a class
    with ``to_dict`` paired with a same-class ``from_dict`` classmethod, or a
    module-level deserializer whose name mentions the class or which constructs it.
    """
    try:
        with open(source_file, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=source_file)
    except (OSError, SyntaxError):
        return []

    pairs: list[tuple[str, str, str]] = []
    to_dict_classes: list[str] = []
    deserializers: list[tuple[str, set[str]]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "to_dict":
                    to_dict_classes.append(node.name)
                elif isinstance(item, ast.FunctionDef) and item.name == "from_dict":
                    pairs.append((node.name, "to_dict", f"{node.name}.from_dict"))
        elif isinstance(node, ast.FunctionDef) and _is_deserializer_name(node.name):
            deserializers.append((node.name, _returned_constructor_names(node)))

    for cls in to_dict_classes:
        if any(p[0] == cls and "from_dict" in p[2] for p in pairs):
            continue
        for deser, returned in deserializers:
            if cls.lower() in deser.lower() or cls in returned:
                pairs.append((cls, "to_dict", deser))
                break

    return pairs


def _is_deserializer_name(name: str) -> bool:
    return "from_dict" in name or "from_d" in name or "_parse_dict" in name


def _returned_constructor_names(node: ast.FunctionDef) -> set[str]:
    """Class names directly constructed in ``return`` statements."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
            func = child.value.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def generate_round_trip_test(
    class_name: str, serialize_method: str, deserialize_func: str, module_path: str
) -> ExecutableProperty:
    """Emit a round-trip property: construct → serialize → deserialize → compare.

    Uses Detective's typed_synthesis to build a non-default constructor; falls
    back to a FILL skeleton when the dataclass can't be resolved.
    """
    from dataclasses import fields as dc_fields

    mod = _module_path(module_path)
    cls = _resolve_dataclass(class_name, mod)
    if cls is None:
        return _round_trip_fallback(class_name, serialize_method, deserialize_func, mod)

    ctor_args = [
        f"{f.name}={synthesize_value(str(f.type) if f.type else '', f.name, mod).code}"
        for f in dc_fields(cls)
    ]
    is_classmethod = "." in deserialize_func
    deser_name = deserialize_func.split(".")[-1]
    deser_call = f"{class_name}.{deser_name}" if is_classmethod else deser_name
    setup = f"from {mod} import {class_name}" + ("" if is_classmethod else f", {deser_name}")

    field_asserts = "\n".join(
        f'assert reconstructed.{f.name} == original.{f.name}, "{f.name} mismatch"' for f in dc_fields(cls)
    )
    assertion = (
        f"original = {class_name}({', '.join(ctor_args)})\n"
        f"serialized = original.{serialize_method}()\n"
        f"reconstructed = {deser_call}(serialized)\n{field_asserts}"
    )
    return ExecutableProperty(
        category="ROUND_TRIP",
        inputs={},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=[f"{class_name}.{serialize_method} ↔ {deserialize_func}"],
        confidence=0.9,
        source_lenses=["pair_detection", "typed_synthesis"],
        needs_oracle=False,
        function_key=f"{module_path}::{class_name}.{serialize_method}",
    )


def _round_trip_fallback(
    class_name: str, serialize_method: str, deserialize_func: str, mod: str
) -> ExecutableProperty:
    return ExecutableProperty(
        category="ROUND_TRIP",
        inputs={},
        setup_code=f"from {mod} import {class_name}",
        assertion_code=(
            f"# Round-trip: {class_name}.{serialize_method}() ↔ {deserialize_func}()\n"
            f"# original = {class_name}(...)\n"
            f"# reconstructed = {deserialize_func}(original.{serialize_method}())\n"
            "# assert reconstructed == original  # FILL"
        ),
        preconditions=["construct instance with non-default values"],
        confidence=0.3,
        source_lenses=["pair_detection"],
        needs_oracle=True,
    )


def _module_path(module_path: str) -> str:
    mod = module_path.replace("/", ".").replace("\\", ".")
    return mod[:-3] if mod.endswith(".py") else mod
