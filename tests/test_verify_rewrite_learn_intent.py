"""§9 second spine source — `verify-rewrite --learn` sources rejected-rewrite censors (#17).

The rejected-rewrite censor source (`censors_from_verification` → `rejected_rewrite_censors`) was BUILT
and unit-tested but had NO production consumer: `verify-rewrite` produced the `RewriteVerification` its
input needs, yet nothing wired the two together, so a CHANGED rewrite's near-misses were observed and
thrown away. These pin the wire's CONTRACT from intent — the exact orchestration the CLI's
`verify-rewrite` branch runs — so a wrong gate (learning on a PRESERVED verdict, or learning with the
flag off) is caught, not just characterized.

`learn_disposition` is the pure gate (converge-pinned separately). The orchestration below is impure
(κ-scoring over the call graph + atomic ledger persistence), so it gets this hand-written durability
test rather than a synth characterization. The full CLI command is exercised end-to-end by hand
(see the commit body); this pins the decision + persistence contract deterministically.
"""

from __future__ import annotations

from Detective.censor import censors_from_verification, learn_disposition
from Detective.promotion_ledger import corpus_fixpoint, ledger_key, load_ledger, save_ledger
from Detective.rewrite import RewriteVerification


def _changed(func: str, diffs: tuple[str, ...]) -> RewriteVerification:
    return RewriteVerification(
        verdict="CHANGED",
        function=func,
        proof_replayed="passed",
        new_dimensions=(),
        differences=diffs,
        abstentions=(),
    )


def _write_hub_pkg(root) -> str:
    """A package where ``f`` reaches ``g`` and ``h`` — so a censor on ``f`` has κ=2 and can promote."""
    (root / "m.py").write_text(
        "def g(x):\n    return x\n\n\ndef h(x):\n    return x + 1\n\n\ndef f(x):\n    return g(x) + h(x)\n"
    )
    return str(root)


# ─── the pure gate: the three dispositions, from intent ───
def test_learn_disposition_gates_on_both_flag_and_verdict():
    # the flag is the primary gate — off means the command writes nothing, whatever the verdict
    assert learn_disposition("CHANGED", False) == "skip_disabled"
    assert learn_disposition("PRESERVED", False) == "skip_disabled"
    # flag on, but a rewrite that PRESERVED behaviour introduced no near-miss to learn from
    assert learn_disposition("PRESERVED", True) == "skip_unchanged"
    assert learn_disposition("ABSTAIN", True) == "skip_unchanged"
    assert learn_disposition("STALE_RECEIPT", True) == "skip_unchanged"
    # only a CHANGED verdict with the flag on sources censors
    assert learn_disposition("CHANGED", True) == "learn"


# ─── the wire: a CHANGED rewrite's near-misses reach the ledger, sourced as rejected_rewrite ───
def test_changed_rewrite_promotes_a_rejected_rewrite_censor_into_the_ledger(tmp_path):
    root = _write_hub_pkg(tmp_path)
    result = _changed("m.py::f", ("f(0)->old0 new9",))
    assert learn_disposition(result.verdict, True) == "learn"

    # the exact sequence the CLI's verify-rewrite --learn branch runs
    censors = censors_from_verification("m.py::f", result)
    assert censors and all(c.source == "rejected_rewrite" for c in censors)
    promoted = corpus_fixpoint(root, censors)["promoted"]
    store = load_ledger(root)
    for e in promoted:
        store[ledger_key(e.censor)] = e
    save_ledger(root, store)

    # f reaches g and h (κ=2) and the source is spine-sourced → the near-miss is fenced and PERSISTED
    reloaded = load_ledger(root)
    rr = [e for e in reloaded.values() if e.censor.source == "rejected_rewrite"]
    assert rr, "a spine-sourced, high-κ rejected-rewrite censor must land in the ledger"
    assert rr[0].censor.func_key == "m.py::f"
    assert rr[0].kappa and rr[0].kappa >= 1


def test_preserved_rewrite_learns_nothing(tmp_path):
    # skip_unchanged: a PRESERVED rewrite carries no forbidden pair, so censors_from_verification is
    # empty and the ledger is never touched — the disposition, not a downstream accident, is the guard.
    root = _write_hub_pkg(tmp_path)
    preserved = RewriteVerification(
        verdict="PRESERVED",
        function="m.py::f",
        proof_replayed="passed",
        new_dimensions=(),
        differences=(),
        abstentions=(),
    )
    assert learn_disposition(preserved.verdict, True) == "skip_unchanged"
    assert censors_from_verification("m.py::f", preserved) == []
    assert load_ledger(root) == {}
