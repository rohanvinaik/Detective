"""Design-warranted tests for Detective.synthesis.oracle_light.

Native tests of the documented oracle-light property generation, mutation-driven
to the ceiling. The generators are string-template functions, so each is called
DIRECTLY (the ``_GENERATORS`` dispatch dict captures function references at module
load, so a mutant reached only via ``generate_executable_property`` is never
exercised) and its FULL output is asserted (every literal is a mutation target).
Plain module-level helpers only (no fixtures).
"""

from __future__ import annotations

import ast

from Detective.synthesis.oracle_light import (
    _boundary_property,
    _build_call,
    _call_args_from_sites,
    _distinct_values,
    _extract_assign_rhs,
    _extract_boundary_info,
    _extract_isinstance_type,
    _extract_self_attr,
    _func_info,
    _generic_property,
    _import_line,
    _other_param_values,
    _parse_diff_changes,
    _skip,
    _state_property,
    _swap_property,
    _swap_type_skip,
    _type_property,
    _value_property,
    generate_executable_property,
    importable_module,
)


def _fn(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


# ── dispatch ──────────────────────────────────────────────────────
def test_dispatch_sets_function_key_and_mutant_id():
    prop = generate_executable_property(
        {"category": "VALUE", "mutant_id": "VALUE_3"}, "m::f", _fn("def f(x):\n return x")
    )
    assert prop.function_key == "m::f" and prop.mutant_id == "VALUE_3"


def test_dispatch_unknown_category_is_generic():
    prop = generate_executable_property({"category": "WEIRD"}, "m::f")
    assert prop.category == "WEIRD" and prop.mutant_id == ""


# ── SWAP ──────────────────────────────────────────────────────────
def test_swap_no_sites_full_output():
    p = _swap_property({}, "m::sub", _fn("def sub(a, b):\n return a - b"), None)
    assert p.category == "SWAP"
    assert p.setup_code == "from m import sub"
    assert p.assertion_code == (
        "result_ab = sub(1, 2)\n"
        "result_ba = sub(2, 1)\n"
        'assert result_ab != result_ba, "SWAP: parameter order should matter"'
    )
    assert p.inputs == {"a": "1", "b": "2"}
    assert p.preconditions == ["a != b", "non-commutative"]
    assert p.confidence == 0.6
    assert p.source_lenses == ["mutation"]
    assert p.needs_oracle is False


def test_swap_with_sites_raises_confidence_and_uses_values():
    p = _swap_property({}, "m::sub", _fn("def sub(a, b):\n return a - b"), [{"positional_args": ["7", "9"]}])
    assert "sub(7, 9)" in p.assertion_code and "sub(9, 7)" in p.assertion_code
    assert p.confidence == 0.75
    assert p.source_lenses == ["mutation", "call_sites"]


def test_swap_fewer_than_two_params_skips():
    p = _swap_property({}, "m::f", _fn("def f(a):\n return a"), None)
    assert p.assertion_code == "# SWAP survived but f has <2 params"
    assert p.confidence == 0.3 and p.needs_oracle is True and p.preconditions == []


def test_swap_distinct_types_skips():
    p = _swap_property({}, "m::f", _fn("def f(a: int, b: str):\n return a"), None)
    assert p.assertion_code == "# SWAP skipped: params have different types (int vs str)"
    assert p.confidence == 0.1 and p.needs_oracle is True


def test_swap_type_skip_none_when_same_type():
    assert _swap_type_skip(_fn("def f(a: int, b: int):\n return a"), "s") is None


def test_swap_type_skip_none_when_missing_annotation():
    assert _swap_type_skip(_fn("def f(a: int, b):\n return a"), "s") is None


# ── BOUNDARY ──────────────────────────────────────────────────────
def test_boundary_extractable_full_output():
    p = _boundary_property(
        {"diff_summary": "- x > 5\n+ x >= 5"}, "m::f", _fn("def f(x):\n return x > 5"), None
    )
    assert p.assertion_code == (
        "result_at = f(5)\n"
        "result_before = f(4)\n"
        'assert result_at != result_before, "BOUNDARY at x=5: > should discriminate"'
    )
    assert p.inputs == {"x": 5}
    assert p.preconditions == ["boundary at x=5 (>)"]
    assert p.confidence == 0.85 and p.needs_oracle is False
    assert p.source_lenses == ["mutation", "diff_analysis"]


def test_boundary_not_extractable_skips():
    p = _boundary_property({"diff_summary": ""}, "m::f", _fn("def f(x):\n return x"), None)
    assert p.assertion_code == "# BOUNDARY survived but boundary value not extractable"
    assert p.confidence == 0.3 and p.needs_oracle is True


# ── TYPE ──────────────────────────────────────────────────────────
def test_type_with_isinstance_full_output():
    p = _type_property(
        {"diff_summary": "- isinstance(x, str)\n+ True"}, "m::f", _fn("def f(x):\n return x"), None
    )
    assert p.setup_code == "from m import f\nimport pytest"
    assert p.assertion_code == (
        "# isinstance checks str on 'x' — wrong type should be rejected\n"
        "with pytest.raises((TypeError, ValueError)):\n"
        "    f(42)"
    )
    assert p.inputs == {"invalid_type": "42"}
    assert p.preconditions == ["isinstance checks str on x"]
    assert p.confidence == 0.7 and p.needs_oracle is False


def test_type_fills_every_param_not_just_the_guarded_one():
    # A short call raises TypeError on ARITY, which property_holds cannot tell apart from
    # the type rejection — it would pass the gate while proving nothing. Every slot is filled.
    p = _type_property(
        {"diff_summary": "- isinstance(a, str)\n+ True"},
        "m::f",
        _fn("def f(a, b):\n return a"),
        [{"positional_args": ["'x'", "9"]}],
    )
    assert p.assertion_code.endswith("f(42, 9)")
    assert p.needs_oracle is False


def test_type_abstains_when_a_slot_cannot_be_filled():
    # No call sites -> the sibling param renders as the `...` Zone-2 residual, so the
    # property is flagged for the CLI to hand back an --input rather than written.
    p = _type_property(
        {"diff_summary": "- isinstance(a, str)\n+ True"}, "m::f", _fn("def f(a, b):\n return a"), None
    )
    assert "..." in p.assertion_code
    assert p.confidence == 0.4 and p.needs_oracle is True


def test_type_abstains_when_isinstance_guards_a_local():
    # `n` is a loop variable, not a parameter: no argument can make it the wrong type, so
    # no test can pin this mutant. Emitting one would raise for an unrelated reason.
    p = _type_property(
        {"diff_summary": "- isinstance(n, str)\n+ True"}, "m::f", _fn("def f(x):\n return x"), None
    )
    assert p.assertion_code == "# TYPE skipped: isinstance guards local 'n', not a param"
    assert p.needs_oracle is True


def test_type_without_isinstance_abstains():
    p = _type_property({"diff_summary": ""}, "m::f", _fn("def f(x):\n return x"), None)
    assert p.assertion_code == "# TYPE survived but the checked type is not extractable"
    assert p.confidence == 0.3 and p.needs_oracle is True


# ── STATE ─────────────────────────────────────────────────────────
def test_state_return_none_full_output():
    p = _state_property({"description": "return_none"}, "m::f", _fn("def f(x):\n return x"), None)
    assert p.assertion_code == (
        'result = f(...)\nassert result is not None, "STATE: return value should not be None"'
    )
    assert p.preconditions == ["function returns a meaningful value"]
    assert p.confidence == 0.7 and p.needs_oracle is False and p.source_lenses == ["mutation"]


def test_state_remove_assign_literal_full_output():
    p = _state_property(
        {"description": "remove_assign", "diff_summary": "- self.count = 5\n+ pass"},
        "m::Counter.reset",
        _fn("def reset(self):\n self.count = 5"),
        None,
    )
    assert p.setup_code == "from m import Counter"
    assert p.assertion_code == "obj = Counter(...)\nobj.reset(...)\nassert obj.count == 5"
    assert p.preconditions == ["construct Counter"]
    assert p.confidence == 0.65 and p.needs_oracle is False
    assert p.source_lenses == ["mutation", "diff_analysis", "state_fast_path"]


def test_state_remove_assign_general_full_output():
    p = _state_property(
        {"description": "remove_assign", "diff_summary": "- self.x = compute()\n+ pass"},
        "m::f",
        _fn("def f(self):\n self.x = 1"),
        None,
    )
    assert p.assertion_code == (
        "# STATE: self.x assignment removed — verify it's set after call\n"
        "# obj = ClassName(...)\n"
        "# obj.f(...)\n"
        "# assert obj.x == EXPECTED  # FILL"
    )
    assert p.preconditions == ["construct object", "verify self.x"]
    assert p.confidence == 0.4 and p.needs_oracle is True
    assert p.source_lenses == ["mutation", "diff_analysis"]


# ── VALUE / generic ───────────────────────────────────────────────
def test_value_full_output():
    p = _value_property({}, "m::f", _fn("def f(x):\n return x"), None)
    assert p.assertion_code == "result = f(...)\nassert result == ...  # FILL: expected value"
    assert p.preconditions == ["exact expected value must be determined"]
    assert p.confidence == 0.3 and p.needs_oracle is True and p.source_lenses == ["mutation"]


def test_generic_full_output():
    p = _generic_property({"category": "WEIRD"}, "m::f", None, None)
    assert p.category == "WEIRD"
    assert p.assertion_code == "# WEIRD mutation survived — manual investigation needed"
    assert p.setup_code == "" and p.confidence == 0.2 and p.needs_oracle is True
    assert p.preconditions == [] and p.source_lenses == ["mutation"]


def test_skip_helper():
    p = _skip("SWAP", "s", "# msg", 0.3)
    assert p.category == "SWAP" and p.setup_code == "s" and p.assertion_code == "# msg"
    assert p.confidence == 0.3 and p.needs_oracle is True and p.inputs == {}


# ── helpers ───────────────────────────────────────────────────────
def test_func_info_strips_self_and_cls():
    assert _func_info("pkg/mod.py::C.m", _fn("def m(self, a, b):\n return a")) == (
        "pkg/mod.py",
        "C.m",
        ["a", "b"],
    )


def test_func_info_no_node():
    assert _func_info("m::f", None) == ("m", "f", [])


def test_import_line_converts_path_to_module():
    assert _import_line("pkg/mod.py", "C.m") == "from pkg.mod import C"


def test_import_line_empty_module():
    assert _import_line("", "f") == ""


def test_import_line_non_py():
    assert _import_line("pkg.mod", "f") == "from pkg.mod import f"


# ── importable_module (the __init__.py walk) ──────────────────────
def _src_layout(tmp_path):
    """A src-layout: `src/` is a source ROOT (no __init__.py), `src/pkg/` is a package."""
    (tmp_path / "src" / "pkg" / "sub").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "sub" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "mod.py").write_text("")
    (tmp_path / "src" / "pkg" / "sub" / "deep.py").write_text("")
    return tmp_path


def test_importable_module_drops_a_source_root_that_is_not_a_package(tmp_path):
    # THE bug: `src/` has no __init__.py, so it is not part of the name. Naming it emitted
    # `from src.pkg.mod import ...`, which imports FINE under PEP 420 namespace packages and
    # is therefore silent — leaving Python holding two module objects for one file.
    root = _src_layout(tmp_path)
    assert importable_module("src/pkg/mod.py", str(root)) == "pkg.mod"


def test_importable_module_keeps_every_directory_that_IS_a_package(tmp_path):
    root = _src_layout(tmp_path)
    assert importable_module("src/pkg/sub/deep.py", str(root)) == "pkg.sub.deep"


def test_importable_module_flat_layout_keeps_the_top_package(tmp_path):
    # No src/ indirection: the package sits at the root and stays in the name.
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text("")
    assert importable_module("pkg/mod.py", str(tmp_path)) == "pkg.mod"


def test_importable_module_top_level_script_is_its_own_name(tmp_path):
    (tmp_path / "calculator.py").write_text("")
    assert importable_module("calculator.py", str(tmp_path)) == "calculator"


def test_importable_module_namespace_dir_without_init_is_not_a_package(tmp_path):
    # A bare directory with no __init__.py anywhere (this author's Genesis tree). The directory
    # is a source root, not a package, so it contributes nothing.
    (tmp_path / "mcp").mkdir()
    (tmp_path / "mcp" / "server.py").write_text("")
    assert importable_module("mcp/server.py", str(tmp_path)) == "server"


def test_importable_module_without_a_root_stays_a_pure_string(tmp_path):
    # root=None cannot touch the filesystem, so it must NOT pretend to know: old behaviour.
    assert importable_module("src/pkg/mod.py") == "src.pkg.mod"


def test_importable_module_already_dotted_is_unchanged(tmp_path):
    assert importable_module("pkg.mod", str(tmp_path)) == "pkg.mod"


def test_import_line_threads_the_root_through_to_the_walk(tmp_path):
    # The whole point of threading `root`: the emitted import must match what the repo types.
    root = _src_layout(tmp_path)
    assert _import_line("src/pkg/mod.py", "f", str(root)) == "from pkg.mod import f"
    assert _import_line("src/pkg/mod.py", "f") == "from src.pkg.mod import f"


def test_parse_diff_changes_pairs_changed_lines():
    assert _parse_diff_changes("- a > 1\n+ a >= 1") == [("a > 1", "a >= 1")]


def test_parse_diff_changes_empty_when_no_marker():
    assert _parse_diff_changes("no diff") == []


def test_extract_boundary_info_int_and_float():
    assert _extract_boundary_info("- n < 10\n+ n <= 10") == {
        "variable": "n",
        "comparator": "<",
        "boundary_value": 10,
    }
    assert _extract_boundary_info("- r > 0.5\n+ r >= 0.5") == {
        "variable": "r",
        "comparator": ">",
        "boundary_value": 0.5,
    }


def test_extract_boundary_info_none():
    assert _extract_boundary_info("- a and b\n+ a or b") is None


def test_extract_isinstance_type():
    assert _extract_isinstance_type("- isinstance(x, int)\n+ True") == "int"
    assert _extract_isinstance_type("- x == 1\n+ x == 2") is None


def test_extract_self_attr():
    assert _extract_self_attr("- self.total = 0\n+ pass") == "total"
    assert _extract_self_attr("- x = 0\n+ pass") is None


def test_extract_assign_rhs_param_and_literals():
    assert _extract_assign_rhs("- self.a = x\n+ pass", ["x"]) == ("param", "x")
    assert _extract_assign_rhs("- self.a = 5\n+ pass", []) == ("literal", "5")
    assert _extract_assign_rhs("- self.a = 'hi'\n+ pass", []) == ("literal", "'hi'")
    assert _extract_assign_rhs("- self.a = None\n+ pass", []) == ("literal", "None")
    assert _extract_assign_rhs("- self.a = compute()\n+ pass", []) is None


def test_distinct_values_from_sites_and_default():
    assert _distinct_values([{"positional_args": ["3", "4"]}]) == ("3", "4")
    assert _distinct_values(None) == ("1", "2")
    assert _distinct_values([{"positional_args": ["5", "5"]}]) == ("1", "2")


def test_other_param_values_excludes_boundary_var():
    assert _other_param_values(["a", "b"], "a", [{"positional_args": ["1", "2"]}]) == {"b": "2"}


def test_build_call_varies_boundary_param():
    assert _build_call("f", ["a", "b"], "a", 5, {"b": "9"}) == "f(5, 9)"
    assert _build_call("f", ["a", "b"], "a", 5, {}) == "f(5, ...)"
    assert _build_call("f", [], None, 5, {}) == "f(5)"


# ── targeted branch coverage ──────────────────────────────────────
def test_type_invalid_value_per_type():
    for typ, invalid in [
        ("int", "'not_int'"),
        ("float", "'not_float'"),
        ("bool", "42"),
        ("list", "42"),
        ("dict", "42"),
        ("tuple", "42"),
    ]:
        p = _type_property(
            {"diff_summary": f"- isinstance(x, {typ})\n+ True"}, "m::f", _fn("def f(x):\n return x"), None
        )
        assert f"    f({invalid})" in p.assertion_code
        assert p.inputs == {"invalid_type": invalid}
        assert p.preconditions == [f"isinstance checks {typ} on x"]


def test_type_unknown_type_defaults_to_none():
    p = _type_property(
        {"diff_summary": "- isinstance(x, Widget)\n+ True"}, "m::f", _fn("def f(x):\n return x"), None
    )
    assert "    f(None)" in p.assertion_code  # unknown type -> None


def test_call_args_from_sites_context():
    assert _call_args_from_sites([{"context": "foo(1, 2)"}]) == "1, 2"
    assert _call_args_from_sites([{"context": "no parens here"}]) == ""
    assert _call_args_from_sites(None) == ""


def test_boundary_float_step_and_output():
    p = _boundary_property(
        {"diff_summary": "- r > 0.5\n+ r >= 0.5"}, "m::f", _fn("def f(r):\n return r > 0.5"), None
    )
    assert "result_at = f(0.5)" in p.assertion_code
    assert "result_before = f(0.4)" in p.assertion_code


def test_boundary_has_unknowns_lowers_confidence():
    # second param has no call-site value -> "..." -> has_unknowns
    p = _boundary_property(
        {"diff_summary": "- x > 5\n+ x >= 5"}, "m::f", _fn("def f(x, y):\n return x > 5"), None
    )
    assert "..." in p.assertion_code and p.confidence == 0.5 and p.needs_oracle is True


def test_state_uses_call_site_args():
    p = _state_property(
        {"description": "return_none"},
        "m::f",
        _fn("def f(x):\n return x"),
        [{"context": "f(7)"}],
    )
    assert "result = f(7)" in p.assertion_code
