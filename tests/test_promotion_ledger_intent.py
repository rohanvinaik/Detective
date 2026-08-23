"""Q1 intent — the corpus self-teaching LEDGER (§14 persistence + promotion), the last Q1 piece.

The ledger is the corpus layer above the per-censor decision core (:mod:`Detective.censor`) and the κ
engine (:mod:`Detective.kappa`): it persists proposed censors, ranks them by marginal-κ over the call
graph, PROMOTES the admissible/high-κ ones greedily, DEMOTES the corpus-vetoed ones, and reaches the κ→0
fixpoint. These pin INTENT (the converge suites only characterize): the promote/demote/halt gate, the
greedy κ subtraction (bulk→tail knee), conservative-emptiness on clean data, the demotion pull, and the
atomic persistence round-trip. Mirrors Regenesis ``promotion_ledger.py`` over CENSORS.
"""

from __future__ import annotations

from Detective import promotion_ledger as pl
from Detective.censor import Censor, harvest_corpus_censors

_PKG_SRC = (
    "def g(a):\n    return a + 1\n\n\n"
    "def f(a, b):\n    return g(a) + b\n\n\n"
    "def caller():\n    return f(1, 2)\n"
)


def _c(func_key: str, source: str = "call_site_absence", subject: str = "arg0=None") -> Censor:
    return Censor(func_key=func_key, kind="input_absent", subject=subject, source=source)


# ─── the fixpoint gate (ledger_disposition) — precedence is the whole point ───
def test_ledger_disposition_precedence_demoted_outranks_everything():
    # A vetoed censor is OUT regardless of how it re-scores this round — the monotone/sticky guarantee.
    assert pl.ledger_disposition("propose", demoted=True, promoted=False) == "skip_demoted"
    assert pl.ledger_disposition("propose", demoted=True, promoted=True) == "skip_demoted"
    assert pl.ledger_disposition("refuse_inadmissible", demoted=True, promoted=False) == "skip_demoted"


def test_ledger_disposition_promoted_is_not_re_ejected_by_a_bad_re_score():
    # Already first-class: a low-κ or inadmissible re-score does NOT eject it — only demotion does.
    assert pl.ledger_disposition("abstain_low_kappa", demoted=False, promoted=True) == "skip_promoted"
    assert pl.ledger_disposition("refuse_inadmissible", demoted=False, promoted=True) == "skip_promoted"


def test_ledger_disposition_fresh_scores_map_to_distinct_codes():
    assert pl.ledger_disposition("propose", demoted=False, promoted=False) == "promote"
    assert pl.ledger_disposition("abstain_low_kappa", demoted=False, promoted=False) == "hold_low_kappa"
    assert pl.ledger_disposition("refuse_inadmissible", demoted=False, promoted=False) == "refuse"
    # the five codes are genuinely distinct (the split is real, not cosmetic)
    codes = {
        pl.ledger_disposition("propose", True, False),
        pl.ledger_disposition("propose", False, True),
        pl.ledger_disposition("refuse_inadmissible", False, False),
        pl.ledger_disposition("abstain_low_kappa", False, False),
        pl.ledger_disposition("propose", False, False),
    }
    assert codes == {"skip_demoted", "skip_promoted", "refuse", "hold_low_kappa", "promote"}


# ─── the halt (fixpoint_reached) ───
def test_fixpoint_reached_only_when_no_promotion_and_no_demotion():
    assert pl.fixpoint_reached(0, 0) is True
    assert pl.fixpoint_reached(1, 0) is False  # a fresh promotion → keep going
    assert pl.fixpoint_reached(0, 1) is False  # a demotion changed the set → re-scan, not a fixpoint
    assert pl.fixpoint_reached(2, 3) is False


# ─── L_ind (self_teaching_fraction), the §16.5 coverage analog ───
def test_self_teaching_fraction_is_confirmed_kappa_over_total_kappa():
    assert pl.self_teaching_fraction([], []) == 0.0  # empty → nothing to teach
    assert pl.self_teaching_fraction([5], [False]) == 0.0  # coverage exists but none self-taught
    assert pl.self_teaching_fraction([5], [True]) == 1.0  # all self-taught
    assert pl.self_teaching_fraction([3, 2], [True, False]) == 0.6  # 3 of 5 self-taught
    assert pl.self_teaching_fraction([0, 0], [True, True]) == 0.0  # zero-coverage → 0, not a div-by-zero


# ─── identity + dedup ───
def test_ledger_key_is_stable_and_distinguishes_source():
    a = _c("m.py::f", source="call_site_absence")
    b = _c("m.py::f", source="rejected_rewrite")
    assert pl.ledger_key(a) == pl.ledger_key(a)  # stable
    assert pl.ledger_key(a) != pl.ledger_key(b)  # a near-miss from a different spine is a different entry


def test_accumulate_dedups_the_same_near_miss():
    c = _c("m.py::f")
    entries = pl.accumulate([c, c, _c("m.py::g")])
    assert len(entries) == 2  # the doubled f-censor collapses to one entry
    assert all(e.kappa is None for e in entries)  # κ unfilled until rank_ledger


# ─── rank_ledger — κ descending, with marginal subtraction against the selected set ───
def test_rank_ledger_orders_by_marginal_kappa_and_subtracts_selected():
    adj = {"f": {"g"}, "g": {"h"}, "h": set(), "leaf": set()}  # f→g→h chain + a leaf
    entries = pl.accumulate([_c("m.py::f"), _c("m.py::leaf")])
    ranked = pl.rank_ledger(adj, entries, selected=[])
    assert [(pl._func_node(e.censor), e.kappa) for e in ranked] == [("f", 2), ("leaf", 0)]
    # with g already selected, f's marginal coverage drops (g and h are already covered)
    ranked2 = pl.rank_ledger(adj, pl.accumulate([_c("m.py::f")]), selected=["g"])
    assert ranked2[0].kappa == 0  # f adds nothing g does not already reach → the bulk→tail knee


# ─── persistence (atomic JSON round-trip; mirrors equivalents' store) ───
def test_load_ledger_is_empty_when_absent(tmp_path):
    assert pl.load_ledger(str(tmp_path)) == {}  # a missing store is no ledger, never an error


def test_save_then_load_round_trips_the_entry(tmp_path):
    c = _c("m.py::f")
    entries = {pl.ledger_key(c): pl.CensorLedgerEntry(censor=c, kappa=3, state="promoted", generation=2)}
    pl.save_ledger(str(tmp_path), entries)
    back = pl.load_ledger(str(tmp_path))
    assert set(back) == set(entries)
    got = back[pl.ledger_key(c)]
    assert got.censor == c and got.kappa == 3 and got.state == "promoted" and got.generation == 2


def test_load_ledger_skips_a_malformed_entry(tmp_path):
    import json

    good = _c("m.py::f")
    store = tmp_path / ".detective" / "censors.json"
    store.parent.mkdir(parents=True)
    store.write_text(
        json.dumps(
            {
                pl.ledger_key(good): {
                    "censor": {
                        "func_key": "m.py::f",
                        "kind": "input_absent",
                        "subject": "arg0=None",
                        "source": "call_site_absence",
                    },
                    "kappa": 1,
                    "state": "proposed",
                    "generation": 0,
                },
                "broken": {"censor": {"func_key": "x"}},  # missing Censor fields → skipped, never fatal
            }
        )
    )
    back = pl.load_ledger(str(tmp_path))
    assert set(back) == {pl.ledger_key(good)}  # the good entry survives; the malformed one is dropped


# ─── the corpus loop over a real call graph ───
def _write_pkg(tmp_path):
    (tmp_path / "m.py").write_text(
        "def h():\n    return 1\n\n\ndef g():\n    return h()\n\n\n"
        "def f():\n    return g()\n\n\ndef leaf():\n    return 42\n"
    )
    return str(tmp_path)


def test_corpus_fixpoint_promotes_the_hub_and_holds_the_leaf(tmp_path):
    root = _write_pkg(tmp_path)
    cf, cl = _c("m.py::f"), _c("m.py::leaf")
    r = pl.corpus_fixpoint(root, [cf, cl])
    assert [pl.ledger_key(p.censor) for p in r["promoted"]] == [pl.ledger_key(cf)]  # f (κ=2) promoted
    assert r["self_teaching"] == 1.0  # all the marginal coverage is in the self-promotable bulk
    assert r["n_demoted"] == 0


def test_corpus_fixpoint_is_conservative_empty_on_zero_kappa(tmp_path):
    # A censor on a leaf (reaches nothing) is the SSL tail — taught, never self-promoted. §14 κ→0 stop.
    r = pl.corpus_fixpoint(_write_pkg(tmp_path), [_c("m.py::leaf")])
    assert r["promoted"] == [] and r["generations"] == 0 and r["self_teaching"] == 0.0


def test_corpus_fixpoint_demotes_a_prior_promotion_the_corpus_now_vetoes(tmp_path):
    root = _write_pkg(tmp_path)
    cf = _c("m.py::f")
    prior = [pl.CensorLedgerEntry(censor=cf, kappa=2, state="promoted", generation=0)]
    r = pl.corpus_fixpoint(root, [cf], prior_promoted=prior, vetoed_keys={pl.ledger_key(cf)})
    assert r["promoted"] == []  # the vetoed prior promotion is pulled and never re-promoted
    assert r["n_demoted"] == 1


def test_corpus_fixpoint_an_inadmissible_censor_never_promotes(tmp_path):
    # engine-derived provenance is refused by the guard regardless of κ (score_censor → refuse_inadmissible).
    bad = Censor("m.py::f", "input_absent", "arg0=None", "engine_derived")
    r = pl.corpus_fixpoint(_write_pkg(tmp_path), [bad])
    assert r["promoted"] == []  # a high-κ but unsourced censor is never fenced

    # and a σ̂-collapsing censor (adoption drives σ̂→0) is refused too, even spine-sourced + high-κ
    r2 = pl.corpus_fixpoint(_write_pkg(tmp_path), [_c("m.py::f")], sigma_hat_after=0)
    assert r2["promoted"] == []


# ─── the corpus harvester (censor.harvest_corpus_censors) — the sourcing side ───
def test_harvest_corpus_censors_fences_absent_none_across_a_package(tmp_path):
    (tmp_path / "m.py").write_text(_PKG_SRC)
    cands = harvest_corpus_censors(str(tmp_path), str(tmp_path))
    subjects = {(c.func_key, c.subject) for c in cands}
    assert ("m.py::f", "arg0=None") in subjects  # f is called f(1, 2), never None → both args fenced
    assert ("m.py::f", "arg1=None") in subjects
    assert all(c.source == "call_site_absence" for c in cands)
    assert not any(c.func_key.endswith("::caller") for c in cands)  # arity 0 → no censor


# ─── the `censor` CLI verb end-to-end (static: bypasses the live pytest session) ───
def test_censor_cli_proposes_read_only_then_promotes_and_lists(tmp_path, capsys):
    from Detective import cli

    (tmp_path / "m.py").write_text(_PKG_SRC)
    root = str(tmp_path)

    assert cli.main(["censor", root, "--project-root", root]) == 0
    out = capsys.readouterr().out
    assert "proposed near-miss" in out and "arg0=None" in out
    assert not (tmp_path / ".detective" / "censors.json").exists()  # read-only: nothing written

    assert cli.main(["censor", root, "--project-root", root, "--promote"]) == 0
    assert (tmp_path / ".detective" / "censors.json").exists()  # --promote persists the ledger

    assert cli.main(["censor", root, "--project-root", root, "--list"]) == 0
    assert "persisted entry" in capsys.readouterr().out


def test_censor_cli_json_proposal_is_machine_readable(tmp_path, capsys):
    import json as _json

    from Detective import cli

    (tmp_path / "m.py").write_text(_PKG_SRC)
    root = str(tmp_path)
    assert cli.main(["censor", root, "--project-root", root, "--json"]) == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["kind"] == "censor-proposal" and payload["proposed"] >= 2
    assert all("disposition" in c and "kappa" in c for c in payload["censors"])
