"""Design-warranted tests for Detective.synthesis.characterization.

The synthesis cluster's correctness oracle is Wesker itself (a synthesized test
is correct iff it kills its mutant), so these are native tests of the documented
semantics, mutation-driven to the ceiling. Plain module-level helpers (not
fixtures) so every test contributes kill power under Wesker.
"""

from __future__ import annotations

from dataclasses import dataclass as _dc

from Detective.synthesis.characterization import (
    GoldenCapture,
    Provenance,
    capture_golden,
    corroborate_captures,
    distinction_pin_lines,
    eval_call_site,
    generate_golden_test,
    golden_assert_line,
)


# ── eval_call_site ────────────────────────────────────────────────
def test_eval_call_site_parses_literals():
    """Literal positional and keyword args evaluate to Python values."""
    assert eval_call_site({"positional_args": ["1", "'x'"], "keyword_args": {"n": "2"}}) == (
        (1, "x"),
        {"n": 2},
    )


def test_eval_call_site_rejects_nonliteral_arg():
    """A non-literal arg (a bare name) makes the whole site uncapturable."""
    assert eval_call_site({"positional_args": ["some_var"]}) is None


def test_eval_call_site_rejects_nonliteral_kwarg():
    """A non-literal kwarg value also fails the whole site."""
    assert eval_call_site({"keyword_args": {"k": "some_var"}}) is None


def test_eval_call_site_passes_through_nonstring_values():
    """Already-evaluated (non-str) values pass through unchanged."""
    assert eval_call_site({"positional_args": [5], "keyword_args": {"k": True}}) == ((5,), {"k": True})


# ── capture_golden ────────────────────────────────────────────────
def _add(a, b):
    return a + b


_nondet_calls: list[int] = []


def _nondet():
    # Genuinely non-deterministic: a growing counter (object() is unreliable —
    # CPython can reuse a freed address, making two reprs match).
    _nondet_calls.append(1)
    return len(_nondet_calls)


def _boom():
    raise ValueError("nope")


def test_capture_golden_deterministic_records_repr():
    """A deterministic call records the result repr and marks it deterministic."""
    caps = capture_golden(_add, [{"positional_args": ["2", "3"]}])
    hit = [c for c in caps if c.inputs == (2, 3)]
    assert hit and hit[0].deterministic is True and hit[0].output == "5"


def test_capture_golden_marks_nondeterministic():
    """An unstable repr across two calls marks the capture non-deterministic."""
    caps = capture_golden(_nondet, [])
    assert caps and caps[0].deterministic is False


def test_capture_golden_skips_raising_invocations():
    """An invocation that raises is not captured."""
    assert capture_golden(_boom, []) == []


def test_capture_golden_dedups_repeated_sites():
    """Identical argument sets are captured once."""
    caps = capture_golden(_add, [{"positional_args": ["1", "1"]}, {"positional_args": ["1", "1"]}])
    assert len([c for c in caps if c.inputs == (1, 1)]) == 1


# ── the write guard is unswallowable (#30, reopened) ──────────────
# The path the target writes to, set per-test; the helper closes over it so it can be a no-arg
# call site (capture_golden runs zero-arg invocations, mirroring _nondet/_boom).
_WRITE_TARGET: list[str] = []


def _writer_that_swallows():
    """A function that writes AND wraps the write in the common `except Exception:` fallback.

    This is the exact shape that used to defeat the speculative-write guard: when the audit hook
    raised the (then-``Exception``-derived) guard mid-write, this handler caught it and returned the
    fallback normally, so Detective pinned a golden of ``'blocked-fallback'`` and reported zero writes.
    """
    try:
        with open(_WRITE_TARGET[0], "w", encoding="utf-8") as fh:
            fh.write("data")
        return "wrote"
    except Exception:  # noqa: BLE001 — deliberately broad: the point is it must NOT catch the guard
        return "blocked-fallback"


def test_write_guard_is_not_swallowed_by_target_except_exception(tmp_path):
    """A target's own `except Exception` must not be able to swallow the speculative-write guard.

    Regression for the reopened #30: with the guard above ``Exception``, the capture is reported as a
    filesystem-writing refusal (non-deterministic, writes named, no pinned value) and the write never
    lands — instead of a bogus deterministic golden of the fallback branch.
    """
    target = tmp_path / "must_not_exist.txt"
    _WRITE_TARGET[:] = [str(target)]
    caps = capture_golden(_writer_that_swallows, [])
    assert caps, "the blocked-write capture must be surfaced, not dropped"
    cap = caps[0]
    assert cap.deterministic is False
    assert cap.filesystem_writes  # the prevented write is named
    # No golden pins the swallowed branch: no value was captured (output is the unset default,
    # never the fallback's ``'blocked-fallback'`` repr).
    assert not cap.output and cap.value is None
    assert cap.output != "'blocked-fallback'"
    assert not target.exists()  # the write was prevented, not merely observed


# ── corroborate_captures ──────────────────────────────────────────
def _provisional(deterministic=True):
    return GoldenCapture(inputs=(1,), output="1", deterministic=deterministic)


def test_corroborate_pure_deterministic():
    """A deterministic capture of a pure function is corroborated as pure_deterministic."""
    out = corroborate_captures([_provisional()], is_pure=True)
    assert out[0].provenance == Provenance.CORROBORATED
    assert out[0].corroborating_lens == "pure_deterministic"


def test_corroborate_value_mutation_killed():
    """A killed VALUE mutation corroborates the golden value."""
    out = corroborate_captures([_provisional()], value_mutation_killed=True)
    assert out[0].provenance == Provenance.CORROBORATED
    assert out[0].corroborating_lens == "mutation_value_killed"


def test_corroborate_pure_requires_determinism():
    """Purity alone does not corroborate a non-deterministic capture."""
    out = corroborate_captures([_provisional(deterministic=False)], is_pure=True)
    assert out[0].provenance == Provenance.PROVISIONAL


def test_corroborate_without_evidence_stays_provisional():
    """No corroborating lens leaves the capture PROVISIONAL."""
    out = corroborate_captures([_provisional()])
    assert out[0].provenance == Provenance.PROVISIONAL


def test_corroborate_passes_through_already_corroborated():
    """A non-PROVISIONAL capture is returned unchanged."""
    cap = GoldenCapture(
        inputs=(1,),
        output="1",
        deterministic=True,
        provenance=Provenance.CORROBORATED,
        corroborating_lens="x",
    )
    assert corroborate_captures([cap]) == [cap]


# ── generate_golden_test ──────────────────────────────────────────
def test_generate_golden_test_pins_exact_value():
    """A deterministic capture becomes an exact repr assertion with the import."""
    cap = GoldenCapture(inputs=(2, 3), output="5", deterministic=True, provenance=Provenance.CORROBORATED)
    src = generate_golden_test("m::add", [cap])
    assert "from m import add" in src
    assert "result = add(2, 3)" in src
    assert "assert result == 5" in src


def test_generate_golden_test_abstains_on_nondeterministic():
    """A non-deterministic capture yields no test — no vacuous skeleton."""
    cap = GoldenCapture(inputs=(), output="<obj>", deterministic=False)
    assert generate_golden_test("m::f", [cap]) == ""


def test_generate_golden_test_tags_provisional():
    """A provisional (uncorroborated) capture carries a provisional tag."""
    cap = GoldenCapture(inputs=(1,), output="1", deterministic=True, provenance=Provenance.PROVISIONAL)
    src = generate_golden_test("m::f", [cap])
    assert "# provisional" in src


def test_generate_golden_test_numbers_multiple_cases():
    """Multiple pinnable captures get distinct numbered test names."""
    caps = [
        GoldenCapture(inputs=(1,), output="1", deterministic=True),
        GoldenCapture(inputs=(2,), output="2", deterministic=True),
    ]
    src = generate_golden_test("m::f", caps)
    assert "def test_f_golden_0():" in src
    assert "def test_f_golden_1():" in src


def test_generate_golden_test_corroborated_docstring():
    """A corroborated capture emits the exact corroborated docstring with its lens."""
    cap = GoldenCapture(
        inputs=(1,),
        output="1",
        deterministic=True,
        provenance=Provenance.CORROBORATED,
        corroborating_lens="pure_deterministic",
    )
    src = generate_golden_test("m::f", [cap])
    assert '"""Golden capture — corroborated via pure_deterministic."""' in src


def test_generate_golden_test_provisional_docstring():
    """A provisional capture emits the exact fossilization-warning docstring."""
    cap = GoldenCapture(inputs=(1,), output="1", deterministic=True, provenance=Provenance.PROVISIONAL)
    src = generate_golden_test("m::f", [cap])
    assert '"""Golden capture — PROVISIONAL (may fossilize bugs)."""' in src


def test_generate_golden_test_unchecked_docstring():
    """An unchecked capture emits the exact unchecked docstring."""
    cap = GoldenCapture(inputs=(1,), output="1", deterministic=True, provenance=Provenance.UNCHECKED)
    src = generate_golden_test("m::f", [cap])
    assert '"""Golden capture — unchecked."""' in src


def test_generate_golden_test_formats_keyword_args():
    """Keyword args are rendered as ``k=repr(v)`` after the positionals."""
    cap = GoldenCapture(inputs=(2,), kwargs={"k": 3}, output="5", deterministic=True)
    src = generate_golden_test("m::f", [cap])
    assert "result = f(2, k=3)" in src


# ── golden_assert_line: nested-set repr stability (dogfood finding, 0.8.6) ──────
# A repr that embeds a set INSIDE a non-literal shell (a dataclass with frozenset
# fields, a list of frozensets) is hash-seed-unstable, and the top-level set guard
# could not see it: the generated test passed or failed on PYTHONHASHSEED.


@_dc(frozen=True)
class _FlowLike:
    uses: frozenset
    must: frozenset


def test_golden_assert_dataclass_with_set_fields_is_seed_stable():
    v = _FlowLike(uses=frozenset({"b", "a"}), must=frozenset())
    line = golden_assert_line(repr(v), v)
    # field access + sorted-element reconstruction: no set repr survives into the test
    assert line == "assert (result.uses, result.must) == (frozenset({'a', 'b'}), frozenset())"
    assert eval(line.removeprefix("assert "), {"result": v})


def test_golden_assert_list_of_frozensets_is_seed_stable():
    v = [frozenset({"y", "x"}), frozenset()]
    line = golden_assert_line(repr(v), v)
    assert line == "assert result == [frozenset({'x', 'y'}), frozenset()]"
    assert eval(line.removeprefix("assert "), {"result": v})


def test_golden_assert_set_of_opaque_objects_still_falls_back_to_repr():
    # elements with no stable reconstruction: the honest fallback stands
    class _Opaque:
        pass

    v = _Opaque()
    line = golden_assert_line(repr(v), v)
    assert line.startswith("assert repr(result) == ")


def test_stable_expr_abstains_on_machine_specific_value():
    """A captured value carrying THIS machine's paths (a Path.resolve()/getcwd()/__file__ result
    baked into a return) must not be pinned — green here, red on any other checkout (#30). Portable
    values, INCLUDING a stable absolute path that is identical everywhere, still pin."""
    import os

    from Detective.synthesis.characterization import _is_machine_specific, _stable_expr

    machine = f"Universe(root='{os.path.expanduser('~')}/proj/data/session', notes='')"
    assert _is_machine_specific(machine)
    assert _stable_expr(machine) is None  # refused
    assert _stable_expr([1, machine]) is None  # refused when nested, too
    assert _stable_expr("hello") == "'hello'"  # a portable value still pins
    assert _stable_expr("/etc/hosts") == "'/etc/hosts'"  # a stable abs path is not machine-specific
    assert _stable_expr(42) == "42"


# ── distinction_pin_lines (the ==-blind-spot ladder) ─────────────────────
def test_pin_lines_scalar_int_vs_float():
    assert distinction_pin_lines(1, "1.0") == ["assert type(result) is int"]


def test_pin_lines_bool_vs_int():
    # True == 1: type() is the only pin that can see it
    assert distinction_pin_lines(True, "1") == ["assert type(result) is bool"]


def test_pin_lines_negative_zero_same_type_pins_repr():
    assert distinction_pin_lines(0.0, "-0.0") == ["assert repr(result) == '0.0'"]


def test_pin_lines_walks_to_the_dict_leaf():
    orig = {"total": 26.33, "points": 1}
    pins = distinction_pin_lines(orig, "{'total': 26.33, 'points': 1.0}")
    assert pins == ["assert type(result['points']) is int"]


def test_pin_lines_walks_nested_lists_and_tuples():
    orig = [(1, 2.0), (3, 4.0)]
    pins = distinction_pin_lines(orig, "[(1, 2.0), (3.0, 4.0)]")
    assert pins == ["assert type(result[1][0]) is int"]


def test_pin_lines_empty_when_values_differ():
    # == already kills; nothing owed
    assert distinction_pin_lines(1, "2") == []


def test_pin_lines_empty_for_raised_marker():
    assert distinction_pin_lines(1, "<raised ValueError: boom>") == []


def test_pin_lines_empty_for_unparseable_object_repr():
    assert distinction_pin_lines(1, "<m.Thing object at 0x1>") == []


def test_pin_lines_pass_on_the_original_and_fail_on_the_mutant():
    # soundness both ways, evaluated live — the property gate runs exactly this
    orig = {"points": 1}
    pins = distinction_pin_lines(orig, "{'points': 1.0}")
    assert all(eval(p.removeprefix("assert "), {"result": {"points": 1}}) for p in pins)
    assert not all(eval(p.removeprefix("assert "), {"result": {"points": 1.0}}) for p in pins)


def test_pin_lines_empty_when_comparison_itself_raises():
    # an original whose __eq__ raises: the guard abstains rather than crash the writer
    class _Cranky:
        def __eq__(self, other):
            raise TypeError("no compare")

        __hash__ = None

    assert distinction_pin_lines(_Cranky(), "1") == []
