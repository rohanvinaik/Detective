"""Intent tests for #78 — NaN and infinity in `--input`, and in everything Detective prints.

The defect, verbatim from the report: ``--input "(0.1, nan, 0.087)"`` was refused (*"`nan` is not a
name in the target module's scope"*), while ``--input "(0.1, np.nan, 0.087)"`` was accepted ONLY
because the target module happened to ``import numpy as np`` — so a module without numpy had no way
to express NaN on the command line. Meanwhile the tool printed its own witnesses with a bare ``nan``,
a spelling its own parser rejected.

Two consequences the report did not name, both measured before the fix:

* the same ``repr`` spelling was pasted into GENERATED tests (``f(x=nan)``), where it is a NameError —
  so ``property_holds`` judged the killing test unsound and it was never written: the survivor came
  back, with the same suggestion, every run;
* converge hands a supplied input to golden capture as ``repr`` strings read back with
  ``literal_eval``, which refuses ``nan`` — the supplied NaN input silently vanished from capture.

The fix reserves ``nan`` / ``inf`` / ``-inf`` / ``float("nan" | "inf" | "-inf")`` in the ONE parser
(``equivalence.parse_input_expression``, shared by the CLI and the ``samples`` reloader) and renders
every printed or generated value through ``literal_source``. The security boundary —
``reject_unsafe_expression``'s grammar gate and dunder ban — is untouched: the reserved spellings are
folded to constants BEFORE it, so they open no evaluation surface (the adversarial tests below).

These are written from intent, not from the implementation: a NaN must survive every hop
(print → paste → parse → store → reload → generated test) as a NaN.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from Detective import samples
from Detective.cli import _parse_supplied_inputs, _witness_args, _witness_input
from Detective.converge import _render_call, property_holds
from Detective.equivalence import (
    InputExpressionError,
    Witness,
    is_expressible,
    literal_source,
    nonfinite_float_spelling,
    parse_input_expression,
    parse_literal_value,
    reject_unsafe_expression,
)
from Detective.synthesis.characterization import eval_call_site


def _same(a: object, b: object) -> bool:
    """NaN-aware equality: two values are the same input when their reprs agree (``repr(nan)`` is
    ``nan`` on both sides), and their types do (``1`` is not ``1.0``)."""
    return repr(a) == repr(b) and type(a) is type(b)


# --- the acceptance: a bare `nan` for a target that imports neither numpy nor math.nan ----------


def test_a_bare_nan_parses_for_a_target_whose_namespace_binds_nothing():
    ns = {"__name__": "fractions_", "fraction_or_default": lambda *a: a}
    args = parse_input_expression("(0.1, nan, 0.087)", ns)
    assert len(args) == 3
    assert args[0] == 0.1 and args[2] == 0.087
    assert isinstance(args[1], float) and math.isnan(args[1])


@pytest.mark.parametrize(
    ("spelling", "expected"),
    [
        ("nan", "nan"),
        ("inf", "inf"),
        ("-inf", "-inf"),
        ('float("nan")', "nan"),
        ("float('inf')", "inf"),
        ("float('-inf')", "-inf"),
        ("float(' Infinity ')", "inf"),
        ("float('-NaN')", "nan"),
    ],
)
def test_every_reserved_spelling_parses_with_and_without_a_namespace(spelling, expected):
    for ns in (None, {}, {"__name__": "m"}):
        (value,) = parse_input_expression(spelling, ns)
        assert isinstance(value, float)
        assert repr(value) == expected


def test_the_spelling_means_the_same_value_whatever_the_target_binds():
    """Namespace-INDEPENDENT, not merely namespace-tolerant: a module that binds its own `nan`, `inf`
    or `float` cannot change what the input language means — and its `float` is never called."""
    called: list[object] = []
    sentinel = object()

    def module_float(*a: object) -> object:
        called.append(a)
        return sentinel

    ns = {"__name__": "m", "nan": sentinel, "inf": sentinel, "float": module_float}
    args = parse_input_expression("(nan, inf, -inf, float('nan'), float('-inf'))", ns)
    assert [repr(a) for a in args] == ["nan", "inf", "-inf", "nan", "-inf"]
    assert all(type(a) is float for a in args)
    assert called == []


def test_the_spellings_nest_inside_containers_and_constructors():
    (value,) = parse_input_expression("{'lo': -inf, 'mid': [nan, 1.5], 'hi': float('inf')}")
    assert repr(value) == "{'lo': -inf, 'mid': [nan, 1.5], 'hi': inf}"


# --- the boundary: these spellings open no evaluation surface -----------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "float('1.5')",  # only the NON-FINITE strings are reserved; `float` is still not an input name
        "float",
        "float.fromhex('0x1p1')",
        "float('nan', 1)",
        "float(x='nan')",
        "float(*['nan'])",
        "nan.__class__",
        "float('nan').__class__",
        "inf.__class__.__mro__[1].__subclasses__()",
        "(nan := 1)",
        "lambda: nan",
        "[x for x in (nan,)]",
        "__import__('os')",
        "().__class__.__mro__[1].__subclasses__()",
    ],
)
def test_a_hostile_input_dressed_in_a_reserved_spelling_is_still_refused(hostile):
    with pytest.raises(InputExpressionError):
        parse_input_expression(hostile, {"__name__": "m"})


def test_the_grammar_gate_itself_still_refuses_what_it_refused():
    """`reject_unsafe_expression` is unchanged: it still sees a bare `nan` NAME as an unknown name
    (the fold happens before it, in the parser), and still bans dunders and non-whitelisted nodes."""
    import ast

    with pytest.raises(InputExpressionError):
        reject_unsafe_expression(ast.parse("nan", mode="eval").body, "nan", {})
    with pytest.raises(InputExpressionError):
        reject_unsafe_expression(ast.parse("(1.5).__class__", mode="eval").body, "(1.5).__class__", {})
    with pytest.raises(InputExpressionError):
        reject_unsafe_expression(ast.parse("[a for a in b]", mode="eval").body, "[a for a in b]", {})


def test_the_spelling_decision_is_textual_and_strict():
    assert nonfinite_float_spelling("nan", False) == "nan"
    assert nonfinite_float_spelling("inf", False) == "inf"
    # A NAME is reserved only as `repr` writes it — `NaN` / `infinity` stay ordinary names.
    assert nonfinite_float_spelling("NaN", False) == "not_reserved"
    assert nonfinite_float_spelling("infinity", False) == "not_reserved"
    assert nonfinite_float_spelling("-inf", False) == "not_reserved"
    # A float() STRING follows float() itself for the non-finite words.
    assert nonfinite_float_spelling(" -Infinity ", True) == "-inf"
    assert nonfinite_float_spelling("+inf", True) == "inf"
    assert nonfinite_float_spelling("-nan", True) == "nan"
    assert nonfinite_float_spelling("1.5", True) == "not_reserved"
    assert nonfinite_float_spelling("", True) == "not_reserved"
    assert nonfinite_float_spelling("nan nan", True) == "not_reserved"


# --- the round trip: print -> parse, store -> reload, generated test -> run -----------------------

_ROUND_TRIP = [
    (0.1, math.nan, 0.087),
    (math.inf,),
    (-math.inf, 2),
    ([math.nan, -math.inf], "x"),
    ({"k": math.nan, math.inf: 1},),
    ((math.nan, (math.inf, [0.5])),),
    (complex(math.nan, 1.0),),
    ({math.nan},),
]


@pytest.mark.parametrize("args", _ROUND_TRIP, ids=repr)
def test_a_printed_witness_round_trips_through_input(args):
    """What `DO THIS --input` prints is accepted by the parser that will receive it, and means the
    input the engine ran — NaN included."""
    witness = Witness(args=args, original="0.0", mutant="1.0")
    rendered = _witness_input(witness)
    assert rendered is not None, f"the printed witness for {args!r} is not an --input the parser accepts"
    (parsed,) = _parse_supplied_inputs([rendered])
    assert len(parsed) == len(args)
    assert all(_same(p, a) for p, a in zip(parsed, args, strict=True))


@pytest.mark.parametrize("args", _ROUND_TRIP, ids=repr)
def test_a_supplied_nan_survives_the_samples_store(args, tmp_path):
    samples.remember(str(tmp_path), "m.py::f", [args])
    (reloaded,) = samples.load(str(tmp_path), "m.py::f")
    assert all(_same(r, a) for r, a in zip(reloaded, args, strict=True))
    # ...and merging it back with the same input supplied again does not duplicate it.
    assert len(samples.merge(str(tmp_path), "m.py::f", [args])) == 1


@pytest.mark.parametrize("args", _ROUND_TRIP, ids=repr)
def test_the_printed_spelling_is_valid_python_for_the_same_value(args):
    """A suggested call is pasted into TESTS too: `literal_source` must be executable Python that
    rebuilds the value, not only an `--input` spelling (a bare `nan` is a NameError there)."""
    source = "(" + _witness_args(Witness(args=args, original="0", mutant="1")) + ")"
    rebuilt = eval(source, {"__builtins__": {"float": float, "complex": complex}})  # noqa: S307
    assert all(_same(r, a) for r, a in zip(rebuilt, args, strict=True))


def test_a_generated_test_at_a_nan_input_runs_and_holds(tmp_path, monkeypatch):
    """The witness test at a NaN input is WRITTEN: its call renders `float('nan')`, so the property
    holds on the real function instead of dying on NameError and being dropped as unsound."""
    (tmp_path / "frac_mod_78.py").write_text(
        "def frac(num, den, default):\n"
        "    if den != den or den <= 0:\n"
        "        return default\n"
        "    return num / den\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    call = _render_call("frac", (0.1, math.nan, 0.087), ("num", "den", "default"))
    assert call == "frac(num=0.1, den=float('nan'), default=0.087)"
    assert property_holds(
        "from frac_mod_78 import frac", f"result = {call}\nassert result == 0.087", str(tmp_path)
    )
    # The pre-fix spelling is exactly what failed: the same property with `repr`'s bare `nan`.
    assert not property_holds(
        "from frac_mod_78 import frac", "result = frac(num=0.1, den=nan, default=0.087)", str(tmp_path)
    )


def test_golden_capture_reads_back_a_supplied_nan():
    """Converge hands supplied inputs to golden capture as `repr` strings; a NaN must read back,
    not vanish as a 'non-literal' call site."""
    parsed = eval_call_site({"positional_args": [repr(0.1), repr(math.nan), repr(-math.inf)]})
    assert parsed is not None
    (num, nan_, ninf), kwargs = parsed
    assert num == 0.1 and math.isnan(nan_) and ninf == -math.inf and kwargs == {}
    assert math.isnan(parse_literal_value("nan"))
    assert eval_call_site({"positional_args": ["some_name"]}) is None  # a real name is still refused


def test_expressible_means_the_parser_accepts_its_spelling():
    """`is_expressible` is "could a user TYPE this": true for every float now; false for the one
    value with no spelling (a non-finite IMAGINARY part), whose printed form the parser refuses."""
    assert is_expressible(math.nan) and is_expressible(-math.inf)
    assert is_expressible(complex(math.inf, 1.0))
    assert not is_expressible(complex(1.0, math.inf))
    with pytest.raises(InputExpressionError):
        parse_input_expression(literal_source(complex(1.0, math.inf)))


def test_values_without_a_nonfinite_float_render_exactly_as_repr():
    """No existing rendering moves: everything without a NaN/inf is byte-identical to `repr`."""
    for value in (1, 1.5, -0.0, "nan", "a'b", [1, (2, 3)], {"k": {1, 2}}, None, True, b"x", 1j, ()):
        assert literal_source(value) == repr(value)


# --- through the real CLI -----------------------------------------------------------------------

_TARGET = '''\
"""A fraction with a default — no numpy, no `math.nan` anywhere in scope (#78)."""


def fraction_or_default(num: float, den: float, default: float) -> float:
    if den != den or den <= 0:
        return default
    return num / den
'''

_TESTS = """\
import fractions_


def test_divides():
    assert fractions_.fraction_or_default(1.0, 2.0, 0.0) == 0.5


def test_non_positive_den_takes_the_default():
    assert fractions_.fraction_or_default(1.0, 0.0, 9.0) == 9.0
"""


def _cli(project: Path, *args: str) -> subprocess.CompletedProcess:
    script = Path(sys.executable).with_name("detective.exe" if sys.platform == "win32" else "detective")
    assert script.is_file(), f"the installed console script is required beside {sys.executable}"
    return subprocess.run(
        [str(script), *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_converge_accepts_a_bare_nan_input_writes_a_runnable_test_and_recalls_it(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "fractions_.py").write_text(_TARGET)
    (project / "tests" / "test_fractions.py").write_text(_TESTS)
    target = "fractions_.py::fraction_or_default"

    supplied = _cli(project, "converge", target, "--input", "(0.1, nan, 0.087)")
    out = supplied.stdout + supplied.stderr
    assert "is not available" not in out, out  # the pre-fix refusal
    assert supplied.returncode == 0, out
    written = list((project / "tests" / "detective").glob("test_fractions__fraction_or_default_*_synth.py"))
    assert len(written) == 1, out
    body = written[0].read_text()
    # The killing test at the supplied NaN input was WRITTEN, in a spelling that runs.
    assert 'den=float("nan")' in body or "den=float('nan')" in body, body
    assert "=nan" not in body.replace(" ", ""), body
    # ...and it passes under real pytest.
    shutil.rmtree(project / ".pytest_cache", ignore_errors=True)
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", str(written[0])],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    final = next(ln for ln in out.splitlines() if ln.startswith("FINAL"))

    # The bare re-run RECALLS the stored NaN input (the store reloads what it wrote) and holds the
    # same verdict — the supplied input did not evaporate on reload.
    bare = _cli(project, "converge", target)
    bare_out = bare.stdout + bare.stderr
    assert bare.returncode == 0, bare_out
    assert "recalled 1 supplied input(s)" in bare_out, bare_out
    bare_final = next(ln for ln in bare_out.splitlines() if ln.startswith("FINAL"))
    assert bare_final == final
    assert written[0].read_text() == body, "the recalled run rewrote a different suite"
