"""Design-warranted tests for Detective.synthesis.characterization.

The synthesis cluster's correctness oracle is Wesker itself (a synthesized test
is correct iff it kills its mutant), so these are native tests of the documented
semantics, mutation-driven to the ceiling. Plain module-level helpers (not
fixtures) so every test contributes kill power under Wesker.
"""

from __future__ import annotations

from Detective.synthesis.characterization import (
    GoldenCapture,
    Provenance,
    capture_golden,
    corroborate_captures,
    eval_call_site,
    generate_golden_test,
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
