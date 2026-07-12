"""Design-warranted tests for oracle_light's swap-gate + round-trip detection,
mutation-driven to the ceiling. Plain module-level helpers only (no fixtures).
"""

from __future__ import annotations

import ast
import os
import tempfile
import textwrap

from Detective.synthesis.oracle_light import (
    _is_deserializer_name,
    _module_path,
    _params_have_distinct_prefixes,
    _returned_constructor_names,
    _round_trip_fallback,
    detect_round_trip_pairs,
    generate_round_trip_test,
    should_emit_swap_test,
)


def _fn(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def _write(code: str) -> str:
    d = tempfile.mkdtemp()
    path = os.path.join(d, "m.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(code))
    return path


# ── should_emit_swap_test ─────────────────────────────────────────
def test_swap_gate_on_swap_survivor():
    assert should_emit_swap_test(_fn("def f(a, b):\n return a"), [{"category": "SWAP"}]) is True


def test_swap_gate_on_non_commutative_pair():
    assert should_emit_swap_test(_fn("def f(start, end):\n return end")) is True


def test_swap_gate_on_distinct_prefixes():
    assert should_emit_swap_test(_fn("def f(static_level, empirical_level):\n return static_level")) is True


def test_swap_gate_declines_generic_params():
    assert should_emit_swap_test(_fn("def f(a, b):\n return a")) is False


def test_swap_gate_declines_single_param():
    assert should_emit_swap_test(_fn("def f(x):\n return x")) is False


def test_swap_gate_declines_no_node_no_survivors():
    assert should_emit_swap_test(None) is False


def test_distinct_prefixes():
    assert _params_have_distinct_prefixes("static_level", "empirical_level") is True
    assert _params_have_distinct_prefixes("a", "b") is False  # single segment
    assert _params_have_distinct_prefixes("x_count", "y_size") is False  # different suffix
    assert _params_have_distinct_prefixes("same_level", "same_level") is False  # same prefix


# ── detect_round_trip_pairs ───────────────────────────────────────
def test_detect_class_from_dict_pair():
    path = _write(
        """
        class Point:
            def to_dict(self):
                return {}
            def from_dict(cls, d):
                return cls()
        """
    )
    assert detect_round_trip_pairs(path) == [("Point", "to_dict", "Point.from_dict")]


def test_detect_module_deserializer_by_name():
    path = _write(
        """
        class Point:
            def to_dict(self):
                return {}

        def point_from_dict(d):
            return None
        """
    )
    assert detect_round_trip_pairs(path) == [("Point", "to_dict", "point_from_dict")]


def test_detect_module_deserializer_by_constructor():
    # `build_from_dict` is a deserializer by name but doesn't mention Widget;
    # it's matched because it constructs Widget in a return.
    path = _write(
        """
        class Widget:
            def to_dict(self):
                return {}

        def build_from_dict(d):
            return Widget()
        """
    )
    assert detect_round_trip_pairs(path) == [("Widget", "to_dict", "build_from_dict")]


def test_detect_none_when_no_pairs():
    assert detect_round_trip_pairs(_write("def f():\n return 1")) == []


def test_detect_prefers_class_from_dict_over_module_deserializer():
    # a class with its own from_dict is not also paired with a module deserializer
    path = _write(
        """
        class Point:
            def to_dict(self):
                return {}
            def from_dict(cls, d):
                return cls()

        def point_from_dict(d):
            return Point()
        """
    )
    assert detect_round_trip_pairs(path) == [("Point", "to_dict", "Point.from_dict")]


def test_detect_ignores_unrelated_deserializer():
    # a deserializer that neither mentions nor constructs the class is not paired
    path = _write(
        """
        class Point:
            def to_dict(self):
                return {}

        def other_from_dict(d):
            return Other()
        """
    )
    assert detect_round_trip_pairs(path) == []


def test_detect_bad_file_returns_empty():
    assert detect_round_trip_pairs("/no/such/file.py") == []


def test_is_deserializer_name():
    assert _is_deserializer_name("from_dict") is True
    assert _is_deserializer_name("thing_parse_dict") is True
    assert _is_deserializer_name("serialize") is False


def test_returned_constructor_names():
    node = _fn("def f(d):\n if d:\n  return Point(d)\n return obj.build()")
    assert _returned_constructor_names(node) == {"Point", "build"}


# ── generate_round_trip_test ──────────────────────────────────────
def test_generate_round_trip_resolvable_dataclass():
    prop = generate_round_trip_test(
        "SynthesizedValue", "to_dict", "SynthesizedValue.from_dict",
        "Detective/synthesis/typed_synthesis.py",
    )
    assert prop.category == "ROUND_TRIP"
    assert "original = SynthesizedValue(" in prop.assertion_code
    assert "serialized = original.to_dict()" in prop.assertion_code
    assert "reconstructed = SynthesizedValue.from_dict(serialized)" in prop.assertion_code
    assert 'assert reconstructed.code == original.code, "code mismatch"' in prop.assertion_code
    assert prop.needs_oracle is False and prop.confidence == 0.9


def test_generate_round_trip_fallback_when_unresolvable():
    prop = generate_round_trip_test("NoSuchClass", "to_dict", "no_from_dict", "m.py")
    assert "# FILL" in prop.assertion_code
    assert prop.needs_oracle is True and prop.confidence == 0.3
    # arg order into _round_trip_fallback matters (class_name first):
    assert prop.setup_code == "from m import NoSuchClass"


def test_swap_gate_method_self_with_non_commutative_pair():
    # `self` is stripped, leaving a non-commutative pair -> emit
    assert should_emit_swap_test(_fn("def m(self, start, end):\n return end")) is True


def test_swap_gate_method_cls_with_non_commutative_pair():
    assert should_emit_swap_test(_fn("def m(cls, start, end):\n return end")) is True


def test_detect_handles_non_method_and_non_function_nodes():
    # a module-level import/assignment and a non-method class member exercise the
    # isinstance/`and` guards (mutating them crashes on nodes without `.name`).
    path = _write(
        """
        import os
        VERSION = 1

        class Point:
            KIND = "2d"
            def to_dict(self):
                return {}
            def from_dict(cls, d):
                return cls()
        """
    )
    assert detect_round_trip_pairs(path) == [("Point", "to_dict", "Point.from_dict")]


def test_round_trip_fallback_exact():
    prop = _round_trip_fallback("Thing", "to_dict", "thing_from_dict", "pkg.mod")
    assert prop.category == "ROUND_TRIP"
    assert prop.setup_code == "from pkg.mod import Thing"
    assert prop.assertion_code == (
        "# Round-trip: Thing.to_dict() ↔ thing_from_dict()\n"
        "# original = Thing(...)\n"
        "# reconstructed = thing_from_dict(original.to_dict())\n"
        "# assert reconstructed == original  # FILL"
    )
    assert prop.preconditions == ["construct instance with non-default values"]
    assert prop.confidence == 0.3 and prop.needs_oracle is True
    assert prop.source_lenses == ["pair_detection"]


def test_generate_round_trip_exact_classmethod():
    prop = generate_round_trip_test(
        "SynthesizedValue", "to_dict", "SynthesizedValue.from_dict",
        "Detective/synthesis/typed_synthesis.py",
    )
    lines = prop.assertion_code.split("\n")
    assert lines[0] == (
        'original = SynthesizedValue(code="test", imports=(), is_placeholder=False, type_name="test")'
    )
    assert lines[1] == "serialized = original.to_dict()"
    assert lines[2] == "reconstructed = SynthesizedValue.from_dict(serialized)"
    assert lines[3] == 'assert reconstructed.code == original.code, "code mismatch"'
    assert lines[-1] == 'assert reconstructed.type_name == original.type_name, "type_name mismatch"'
    assert prop.setup_code == "from Detective.synthesis.typed_synthesis import SynthesizedValue"
    assert prop.preconditions == ["SynthesizedValue.to_dict ↔ SynthesizedValue.from_dict"]
    assert prop.source_lenses == ["pair_detection", "typed_synthesis"]
    assert prop.function_key == "Detective/synthesis/typed_synthesis.py::SynthesizedValue.to_dict"


def test_generate_round_trip_module_deserializer_setup():
    # a non-classmethod deserializer is imported alongside the class
    prop = generate_round_trip_test(
        "SynthesizedValue", "to_dict", "sv_from_dict", "Detective/synthesis/typed_synthesis.py"
    )
    assert prop.setup_code == "from Detective.synthesis.typed_synthesis import SynthesizedValue, sv_from_dict"
    assert "reconstructed = sv_from_dict(serialized)" in prop.assertion_code


def test_swap_gate_three_params_uses_first_two():
    # only params[:2] gate; a non-commutative first pair still emits with a 3rd param
    assert should_emit_swap_test(_fn("def f(start, end, step):\n return step")) is True


def test_swap_gate_prefix_only_second_pair_declines():
    # first two params commute; the gate must not peek past [:2]
    assert should_emit_swap_test(_fn("def f(a, b, static_x, dynamic_x):\n return a")) is False


def test_module_path_normalization():
    assert _module_path("pkg/mod.py") == "pkg.mod"
    assert _module_path("pkg.mod") == "pkg.mod"
