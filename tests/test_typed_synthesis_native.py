"""Design-warranted tests for Detective.synthesis.typed_synthesis.

Native tests of the documented resolution semantics, mutation-driven to the
ceiling. Plain module-level helpers only (no fixtures), so every test contributes
kill power under Wesker.
"""

from __future__ import annotations

from Detective.synthesis.typed_synthesis import (
    SynthesizedValue,
    _dataclass_construction,
    _fallback,
    _heuristic_value,
    _parse_annotation,
    synthesize_value,
)

# A real, importable dataclass to exercise the dataclass resolution path.
_THIS_MODULE = "Detective.synthesis.typed_synthesis"


# ── primitives ────────────────────────────────────────────────────
def test_str_default():
    assert synthesize_value("str").code == '""'


def test_str_uses_name_heuristic_for_path():
    assert synthesize_value("str", "file_path").code == '"test.py"'


def test_str_uses_name_heuristic_for_key():
    assert synthesize_value("str", "cache_key").code == '"test"'


def test_int_float_bool_bytes():
    assert synthesize_value("int").code == "0"
    assert synthesize_value("float").code == "0.0"
    assert synthesize_value("bool").code == "False"
    assert synthesize_value("bytes").code == 'b""'


def test_none_annotation():
    v = synthesize_value("None")
    assert v.code == "None" and v.is_placeholder is False


# ── containers ────────────────────────────────────────────────────
def test_bare_list_is_empty():
    assert synthesize_value("list[int]").code == "[]"  # primitive inner -> empty


def test_list_of_dataclass_populates_one_element():
    v = synthesize_value("list[SynthesizedValue]", module_path=_THIS_MODULE)
    assert v.code.startswith("[SynthesizedValue(") and v.code.endswith("]")
    assert v.type_name == "list[SynthesizedValue]"


def test_dict_set_tuple():
    assert synthesize_value("dict[str, int]").code == "{}"
    assert synthesize_value("set[int]").code == "set()"
    assert synthesize_value("tuple[int, str]").code == "()"


# ── optional / union / any ────────────────────────────────────────
def test_optional_unwraps_inner():
    assert synthesize_value("Optional[int]").code == "0"


def test_bare_optional_is_none():
    assert synthesize_value("Optional").code == "None"


def test_union_uses_non_none_branch():
    assert synthesize_value("int | None").code == "0"
    assert synthesize_value("None | int").code == "0"


def test_any_falls_back():
    v = synthesize_value("Any", "count")
    assert v.is_placeholder is True and v.code == "0"


# ── dataclass resolution ──────────────────────────────────────────
def test_dataclass_minimal_construction_via_synthesize():
    v = synthesize_value("SynthesizedValue", module_path=_THIS_MODULE)
    assert v.code.startswith("SynthesizedValue(")
    assert v.imports == (f"from {_THIS_MODULE} import SynthesizedValue",)
    assert v.is_placeholder is False


def test_dataclass_construction_fills_only_required_fields():
    # SynthesizedValue: only `code` is required (no default); imports/is_placeholder/type_name have defaults.
    code, imports = _dataclass_construction(SynthesizedValue)
    assert code.startswith("SynthesizedValue(code=") and "imports=" not in code
    assert imports == (f"from {_THIS_MODULE} import SynthesizedValue",)


def test_unresolvable_type_falls_back():
    v = synthesize_value("NoSuchType", "name", module_path=_THIS_MODULE)
    assert v.is_placeholder is True and v.code == '"test"'


# ── fallback heuristics ───────────────────────────────────────────
def test_fallback_by_name():
    assert synthesize_value("", "output_path").code == '"test.py"'
    assert synthesize_value("", "user_name").code == '"test"'
    assert synthesize_value("", "item_count").code == "0"
    assert synthesize_value("", "is_ready").code == "False"


def test_fallback_unknown_is_none_placeholder():
    v = synthesize_value("", "widget")
    assert v.code == "None" and v.type_name == "unknown" and v.is_placeholder is True


# ── annotation parsing ────────────────────────────────────────────
def test_parse_annotation_simple_and_generic():
    assert _parse_annotation("int") == ("int", [])
    assert _parse_annotation("list[int]") == ("list", ["int"])
    assert _parse_annotation("dict[str, int]") == ("dict", ["str", "int"])


def test_parse_annotation_invalid_returns_empty():
    assert _parse_annotation("!!!") == ("", [])


# ── heuristic helpers, discriminating (single-keyword) names ───────
def test_heuristic_value_each_branch():
    assert _heuristic_value("name_x") == '"test"'
    assert _heuristic_value("x_key") == '"test"'
    assert _heuristic_value("config_file") == '"test.py"'  # file, not path
    assert _heuristic_value("the_path") == '"test.py"'
    assert _heuristic_value("err_msg") == '"test message"'  # msg, not message
    assert _heuristic_value("a_message") == '"test message"'
    assert _heuristic_value("x", "int") == "1"
    assert _heuristic_value("x", "integer") == "1"
    assert _heuristic_value("x", "float") == "1.0"
    assert _heuristic_value("x", "bool") == "False"
    assert _heuristic_value("x", "str") == '"test"'


def test_fallback_each_branch():
    def chk(name: str, code: str, type_name: str) -> None:
        v = _fallback(name)
        assert v.code == code and v.type_name == type_name and v.is_placeholder is True

    chk("the_path", '"test.py"', "str")
    chk("a_file", '"test.py"', "str")  # file, not path
    chk("out_dir", '"test.py"', "str")  # dir, not path/file
    chk("the_name", '"test"', "str")
    chk("a_key", '"test"', "str")  # key, not name
    chk("the_count", "0", "int")
    chk("num_x", "0", "int")  # num, not count
    chk("x_size", "0", "int")  # size, not count/num
    chk("the_flag", "False", "bool")
    chk("enable_x", "False", "bool")  # enable, not flag
    chk("is_x", "False", "bool")  # is_, not flag/enable
    chk("widget", "None", "unknown")
