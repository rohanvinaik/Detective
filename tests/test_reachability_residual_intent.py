"""Reachability (RIP-R) and expressibility (§6) route a candidate-equivalent AWAY from a false flag (#67).

A candidate-equivalent survivor — no distinguishing input found — is NOT one thing, and flagging one
``equivalent`` when it is really killable-but-unreached is a FALSE specification claim (the #67 hazard).
Two negative-entropy signals the witness search already computes, and used to DISCARD at the disposition,
tell the kinds apart (§6, the expressibility boundary; Def. 1.4's Reachability–Infection–Propagation):

  * ``reached`` (RIP-R) — was the mutant's mutated line EXECUTED by any tried input? A survivor whose
    mutation never ran is killable with a REACHING input the search did not construct (a branch behind
    ``len(items) > 5`` the seq-length grid never builds), NOT an equivalence. ``classify_survivors`` traces
    the ORIGINAL over the final pool (``_reached_lines``) and marks each candidate-equivalent's ``reached``.
  * ``inputs_expressible`` (§6 door 3) — does the exercising value have an ``--input`` literal form? False
    ⇒ a domain-object function (``serialize_rule``); no ``--input`` differentiates → a hand-built fixture,
    never a flag.

The signals are SIGN-AGNOSTIC: they gate any candidate-equivalent — a positive mutant OR a μ⁻ ``OUTPUT``
perturbation — because both are ``residual_disposition``'s subject. ``genuine_equivalent`` (flag-safe) is
now minted ONLY when the mutation was REACHED over EXPRESSIBLE inputs.
"""

from __future__ import annotations

from Detective.engine import classify_survivors
from Detective.equivalence import _reached_lines, residual_disposition


# ── the reachability tracer: production of the RIP-R signal ─────────────────────────
def _toy(src: str) -> dict:
    ns: dict = {}
    exec(compile(src, "/tmp/toy_reach_intent.py", "exec"), ns)  # noqa: S102 — a fixed toy, not user input
    return ns


def test_reached_lines_misses_a_branch_the_pool_never_enters():
    f = _toy("def f(x):\n    if x == 42:\n        return 'hit'\n    return 'miss'\n")["f"]
    fn = f.__code__.co_filename
    # line 3 (the return behind `x == 42`) is UNREACHED by [0, 1] and REACHED by [42]; line 4 always runs.
    assert 3 not in _reached_lines(f, [(0,), (1,)], fn, frozenset({3}), 2.0)
    assert 3 in _reached_lines(f, [(0,), (42,)], fn, frozenset({3}), 2.0)
    assert 4 in _reached_lines(f, [(0,)], fn, frozenset({4}), 2.0)


def test_reached_lines_is_additive_on_a_missing_file_or_empty_target():
    # Best-effort SIGNAL: an unknown filename or no target lines → empty, so a line reads "unreached" and
    # only ADDS a caveat, never suppresses one (the principled-abstention direction of `blocked`/`undefined`).
    g = _toy("def g(x):\n    return x\n")["g"]
    assert _reached_lines(g, [(0,)], None, frozenset({2}), 2.0) == frozenset()
    assert _reached_lines(g, [(0,)], g.__code__.co_filename, frozenset(), 2.0) == frozenset()


# ── end-to-end: an unreached candidate-equivalent is marked, and never flag-safe ────
_PICK = (
    "def pick(items: list) -> int:\n"
    "    if len(items) > 5:\n"
    "        return items[5] * 100  # unreached: the seq-length grid builds len 0..2, never >5\n"
    "    return 0\n"
)


def _write_pick(tmp_path) -> str:
    (tmp_path / "pick.py").write_text(_PICK)
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "test_pick.py").write_text(
        "from pick import pick\n\n\n"
        "def test_pick():\n"
        "    assert pick([]) == 0\n"
        "    assert pick([1, 2]) == 0\n"
    )
    return str(tmp_path)


def test_unreached_candidate_equivalent_is_marked_and_never_flag_safe(tmp_path):
    rep = classify_survivors("pick.py", "pick", _write_pick(tmp_path), deadline_s=None)
    # The mutants on `items[5] * 100` sit behind `len(items) > 5`; the grid never builds a long enough
    # list, so the ORIGINAL never executes that line — those survivors come back reached=False.
    unreached = [v for v in rep.candidate_equivalent if not v.reached]
    assert unreached, "expected an unreached candidate-equivalent behind the len>5 branch"
    # Its inputs ARE expressible (a short list exercises pick), so WITHOUT reachability every survivor
    # would be flat + expressible ⇒ genuine_equivalent ⇒ flag-eligible. Reachability is the negative-
    # entropy that routes it to structural_residual instead — killable with a reaching input, NEVER a flag.
    assert rep.inputs_expressible is True
    for v in unreached:
        assert (
            residual_disposition(False, False, "flat", reached=v.reached, inputs_expressible=True)
            == "structural_residual"
        )


def test_reachability_is_sign_agnostic_marks_two_sign_survivors_too(tmp_path):
    # The signal gates ANY candidate-equivalent, positive OR μ⁻: the two-sign run marks `reached` the
    # same way (an OUTPUT perturbation behind the unreached branch is not flag-safe either).
    rep = classify_survivors("pick.py", "pick", _write_pick(tmp_path), deadline_s=None, two_sign=True)
    assert any(not v.reached for v in rep.candidate_equivalent), (
        "the two-sign run must also mark the unreached survivors reached=False"
    )
