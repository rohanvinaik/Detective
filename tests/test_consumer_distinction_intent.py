"""The class-wide distinction fence: every consumer distinguishes a decision's codes, or says why not.

COMMUNICATING_DETERMINISM §9 invariant 3 (EP-G1, docs/ENGINEERING_PASS_2026-09-26.md):

    Every consumer distinguishes all of a decision's codes, or names the ones it deliberately
    collapses and why.

§3.2 called this decidable over the reference graph and unbuilt; §11 listed it as open. It was found
by hand twice. `certify._TERMINAL_STANDINGS` admitted three of the five codes `certificate_standing`
produces, and the other two fell through into codes meaning absence. The anti-drift test written to
catch exactly that called the function over the subspace where the two surfaces cannot disagree. A
failure of this kind keeps every suite green, because the tests assert the message emitted and not
the distinction lost.

The registries follow `test_pinned_decision_consumption_intent.py`, and for its reason: *"the
solution isn't to hide from the dark, it's to throw some light on it"* (founder ruling 2026-09-09).
An entry takes a REASON, never a bare name. The reason says, in terms a reader can check against the
code, why the codes the site leaves to one fall-through do not need telling apart there. The split:

    BY_DESIGN  the collapse is intended. Its reason is already written in the code (a docstring or a
               comment, quoted), or the merged codes cannot arise at that call site (the arguments
               or an earlier return rule them out, stated).
    OPEN       the code documents the distinction as one a reader or a later step needs, and this
               site loses it or re-derives it. Real gaps, carried in the open for the founder. A
               ruling moves an entry to BY_DESIGN with the founder's reason, or a fix deletes it
               (`collapse_stale` makes the deletion compulsory).

WHAT THIS IS NOT. It does not judge whether a collapse is right. It answers one countable question,
"which sites merge codes without saying why", and hands the meaning to a person.
"""

from __future__ import annotations

import textwrap

import pytest

from Detective.distinction import (
    COLLAPSE_STALE,
    COLLAPSES,
    DISTINGUISHES_ALL,
    FORWARDS,
    PHANTOM_CODE,
    closed_decision_count,
    consumer_reads,
    distinction_disposition,
)

BY_DESIGN: dict[str, str] = {
    "equivalents.contract_disposition @ engine.classify_survivors._split": (
        "Cannot arise here. `_split` calls it with buildable=killable=blocked=False (its docstring: "
        "'contract_disposition with buildable=killable=blocked=False decides'), and with `buildable` "
        "False the decision returns only `equivalent`, `fence` or `unclassified`: `killable` and "
        "`candidate` need a buildable mutant. The else stands for `unclassified` alone, as its comment says."
    ),
    "extract.extract_readiness @ extract.render_extract": (
        "Cannot arise here. A proposal exists only for a survey finding, and `survey._survey_finding` "
        "returns None for a `reachable` disposition, so `reachable` never reaches this call. The else "
        "stands for `no_primitive_seam` alone, as its comment says."
    ),
    "capture.harvest_disposition @ capture.capture_call_inputs": (
        "Both stop the harvest and keep what was captured, which is the decision's own rule ('a partial "
        "harvest is honest, an overrun is not'); the function returns inputs, not how it ended. The wall "
        "is the classifier's `_cls_abs_deadline`, which the classifier reads again for itself "
        "(`_cls_exhausted()`, and the witness search's `deadline=`), so the cut is visible to the "
        "classification that consumes the harvest."
    ),
    "promotion_ledger.ledger_disposition @ promotion_ledger.corpus_fixpoint": (
        "A first-admissible search: every code but `promote` means 'not this entry this round', and the "
        "loop emits nothing per entry. The decision's docstring gives the split's purpose as pinning the "
        "gates' order ('a re-merge (e.g. letting a demoted censor re-promote) fails a pin'), not rendering."
    ),
    "suite_edit.nodeid_kind @ suite_edit.apply_removals": (
        "A filter: only `parametrized_case` is set aside here, and the comment above it says why. The "
        "other three go on to `_locate`, which resolves each through `nodeid_function_name` and "
        "`nodeid_file_hint`: a `qualified` id pins its file, a `bare` one matches any in-root "
        "definition, and an `empty` one matches no callable and is reported not_found."
    ),
    "converge.owned_obligation_disposition @ converge._self_owned_obligation_ids._mutant_kept": (
        "Stated by the accessor's docstring: it 'drops only the foreign_only ones … KEPT: owned … AND "
        "unwitnessed (a kill with no recorded killer is this target's kill, not a foreign dependency — "
        "never dropped for missing attribution)'. This is the one call site of the foreign_only / "
        "unwitnessed split, and it keeps those two apart. For review: the decision's own docstring says "
        "`unwitnessed` is 'never invented into the receipt'."
    ),
    "capture.profile_hook_disposition @ capture.capture_call_inputs": (
        "`install` and `install_and_restore` take the same action: `sys.setprofile(prev)` in the "
        "`finally` reinstates None and a Python callable alike, so the split names which state is handed "
        "back and no remedy differs. `foreign_unrestorable` is the one code with a different remedy, and "
        "it is the one compared (EP-B2)."
    ),
    "capture.profile_hook_disposition @ capture.capture_return_types": (
        "The same reading as the input harvest: `sys.setprofile(prev)` restores None and a Python "
        "callable alike, and `foreign_unrestorable`, the only code whose remedy differs, is the one "
        "compared (EP-B2)."
    ),
    "reachability.reach_disposition @ reachability.reachable_test_paths": (
        "A filter whose question is the decision's own first line, 'may a collected test execute the "
        "target's lines?': `direct` and `fixture` both keep the test, which is the soundness property "
        "its docstring states (never drop a fixture-mediated reacher). The split pins the fixture path "
        "as its own evidence, so a change that stops recognising it fails the pin."
    ),
    "reachability.within_declared_testpaths @ reachability.reachable_test_paths": (
        "A filter on 'would pytest collect this file': `unrestricted` (no testpaths declared, so pytest "
        "walks the whole tree) and `within` both answer yes. `foreign` is the one excluded, and the "
        "comment on the `continue` says why."
    ),
    "equivalence.residual_disposition @ cli.candidate_equivalent_caveat": (
        "Cannot arise here. The call passes is_killable=False and is_crash_only=False, so `killer_ready` "
        "and `value_residual` are unreachable. Of the three that remain, `fixture_residual` and "
        "`structural_residual` are named, and the fall-through `none` stands for `genuine_equivalent` alone."
    ),
    "engine.search_pool_admission @ engine._admit_search_pool": (
        "Both admit codes put the test in the pool. `defer_shaped`, the one code with a different "
        "action, is counted and returned so the caller discloses it (the consumer's docstring: "
        "'deferral is never a silent drop')."
    ),
    "ledger.suite_state_comparison @ doctor.same_recorded_state": (
        "Stated in the consumer's docstring: it 'Returns a BOOL, against the house rule, because "
        '`spiral_disposition`\'s signature takes one … `unknown` maps to "changed", which keeps a state '
        "nobody can establish QUIET rather than letting it accuse — the safe direction "
        "`INVOCATION_LEDGER.md` §7.1 named'."
    ),
    "call_sites.usage_evidence_class @ survey._param_unresolved": (
        "A predicate whose question is whether a parameter's type is an OPEN question; its docstring "
        "keeps it apart from `_param_inexpressible` so an unproven case is not put behind a proven one's "
        "name. `resolved` and `none` both answer no. Which type was resolved is `usage_inferred_type`'s "
        "answer, read by `_param_inexpressible`."
    ),
    "call_sites.usage_inferred_type @ extract._extraction_inputs": (
        "A type-class question over a type NAME: is the parameter a scalar (`in {'bool', 'int', 'float', "
        "'str', 'bytes'}`)? `ndarray` is not one and `''` (unknown) is not established as one; both keep "
        "the parameter out of the primitive set, which sends it to `unresolved`, the conservative direction."
    ),
    "characterization.value_capture_coupling @ converge._golden_properties": (
        "Stated by the decision's docstring: with `value_local` the witness pass is 'correctly left open "
        "rather than shut for a reason already handled per-value', and `none` is no objection. Only "
        "`function_coupled` shuts it, and it is the one compared."
    ),
    "emission.value_portability @ emission.c_literal": (
        "Stated by the consumer's docstring: '``None`` for anything `value_portability` does not call "
        "portable — the codec never guesses.' The render half of the codec asks one question: portable "
        "or not."
    ),
}

# The code documents these distinctions as ones a reader or a later step needs, and each site loses
# or re-derives them. Eight on 2026-09-26, the day the guard was built; two resolved the same day by
# fixes their decisions' docstrings already dictated (EP-G4: `decompose_terminal`, `parameter_scope`
# now dispatch on the code). The founder rules on the rest.
OPEN: dict[str, str] = {
    "array_inputs.array_source_disposition @ array_inputs.array_source": (
        "`finite` and `exact` are passed as the constants True, True, so two pinned branches cannot fire "
        "from production: exactness is pre-guarded by the `type(value) is ndarray` check, and finiteness "
        "is re-derived inline AFTER the decision (`numpy.isfinite`), beside a float-width gate — the gate "
        "that runs is unpinned. The reachable refusals `outside_bound` and `unsupported_dtype` both become "
        "None and nothing reports which. Question: pass the measured facts in (the finiteness read must "
        "stay behind the dtype check, since isfinite rejects object dtypes), and does a reader need the "
        "reason?"
    ),
    "censor.learn_disposition @ cli._run_verify_rewrite": (
        "The decision's docstring: 'the two skips are distinct so a reader sees WHY nothing was learned "
        "(flag off vs. rewrite clean)'. The only consumer prints a line for `learn` alone, so `--learn` on "
        "a verdict other than CHANGED prints nothing and the WHY reaches no one. Question: what the "
        "`skip_unchanged` line says (`skip_disabled` is the flag being off, which needs no line)."
    ),
    "converge.regression_recovery @ converge._converge_impl": (
        "Asked once, with retried=False, and only `retry_unminimized` is compared. After the retry, "
        "`ship` versus `restore_prior` is decided by re-reading `regressed` (`if regressed:`), never by "
        "asking the decision with retried=True, so its retried branch is pinned and unreached from "
        "production. The behaviour agrees today. Remedy: ask it again after the retry, dispatch on the code."
    ),
    "rewrite.rewrite_classification_status @ rewrite.verify_rewrite": (
        "Three reasons classification could not run (`unavailable`: no report; `load_failed`; "
        "`invalid_measurement`) become one bool, `classification_ran`, and one sentence ('survivor "
        "classification could not run on the rewritten source — abstaining'). A load failure is fixed "
        "in the environment and an invalid measurement by re-running (exit 2 against 3 in §4's "
        "alphabet), the shape of §3.1's verify-rewrite exit-2 collision. Question: should the verdict or "
        "its sentence carry the reason?"
    ),
    "doctor.signpost_disposition @ cli._signpost_rows": (
        "Asked with green=True, red=False, yellow=False, where only `preempted_by_setup`, `emit` and "
        "`unknown_herb` can arise. `unknown_herb` falls through with `emit` into `return []`, so the "
        "command speaks with no signpost. The decision's docstring: unknown_herb is 'NAMED, never admitted "
        "by fall-through. A command whose herb nobody declared must not silently acquire permission to "
        "speak'. Reachable only for a verb missing from COMMAND_HERB, which is the drift it exists to name."
    ),
    "emission.value_portability @ emission.run_c_gate": (
        "`numeric_model_risk` and `inexpressible` (and any return that is not an int) are summed into one "
        "`skipped` count. The decision's docstring gives them different standings: `numeric_model_risk` "
        "is 'skipped and COUNTED (the modulo qualifier)', `inexpressible` is 'codec v2 territory, named "
        "and deferred'. Question: should the gate count them apart?"
    ),
}


@pytest.fixture(scope="module")
def reads():
    """One AST pass over the package."""
    return consumer_reads("Detective")


def _disposition(read, reason: str = "") -> str:
    return distinction_disposition(list(read.codes), list(read.distinguished), read.forwards, reason)


# ---------------------------------------------------------------- the fence


def test_every_collapsing_site_is_distinguished_or_carries_a_reason(reads) -> None:
    """THE guard. A site that sends two or more codes down one path, with nothing on record saying
    why, is the `_TERMINAL_STANDINGS` shape, and it passes every other check in this repo."""
    unexplained = [
        r for r in reads if _disposition(r) == COLLAPSES and r.key not in BY_DESIGN and r.key not in OPEN
    ]
    assert not unexplained, (
        "consumer(s) that merge two or more of a decision's codes with no recorded reason:\n  "
        + "\n  ".join(
            f"{r.key}  ({r.location}) names {list(r.distinguished)}, merges "
            f"{sorted(set(r.codes) - set(r.distinguished))}"
            for r in unexplained
        )
        + "\n\nDistinguish them, or add the site to BY_DESIGN/OPEN with a reason a reader can check."
    )


def test_no_site_compares_against_a_code_its_decision_cannot_return(reads) -> None:
    """A comparison that can never be true is drift: the decision renamed a code and this consumer
    still names the old one, so the state it meant to catch now falls through. No reason excuses it."""
    recorded = {**BY_DESIGN, **OPEN}
    phantoms = [r for r in reads if _disposition(r, recorded.get(r.key, "")) == PHANTOM_CODE]
    assert not phantoms, "\n".join(
        f"{r.key} ({r.location}) compares against {sorted(set(r.distinguished) - set(r.codes))}, "
        f"which {r.decision} never returns (it returns {list(r.codes)})"
        for r in phantoms
    )


def test_the_population_is_not_silently_shrinking(reads) -> None:
    """A broken reading drops sites out of the population the guard claims to cover. Pinned loosely:
    it moves as decisions are added, and a COLLAPSE of the count is what this catches."""
    closed, declared = closed_decision_count("Detective")
    assert closed > 80, f"only {closed} of {declared} declared decisions read as closed code sets"
    assert len(reads) > 90, f"only {len(reads)} consumer sites found"


def test_every_site_has_one_key(reads) -> None:
    """A registry entry names a site by its key; two sites under one key would share an excuse."""
    keys = [r.key for r in reads]
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------- the registries cannot rot


def test_no_registry_entry_names_a_site_that_no_longer_collapses(reads) -> None:
    """`collapse_stale`. An excuse that outlived its collapse is a finding, not a tidy no-op."""
    by_key = {r.key: r for r in reads}
    stale = [
        key
        for key, reason in {**BY_DESIGN, **OPEN}.items()
        if key in by_key and _disposition(by_key[key], reason) == COLLAPSE_STALE
    ]
    assert not stale, f"these sites no longer collapse; delete their registry entries: {stale}"


def test_no_registry_entry_names_a_site_that_no_longer_exists(reads) -> None:
    """The other way a registry rots: the consumer was renamed, moved or deleted, and its excuse
    silently covers nothing."""
    keys = {r.key for r in reads}
    ghosts = [key for key in {**BY_DESIGN, **OPEN} if key not in keys]
    assert not ghosts, f"registry names sites that do not exist any more: {ghosts}"


def test_every_reason_actually_says_something() -> None:
    for key, reason in {**BY_DESIGN, **OPEN}.items():
        assert len(reason.strip()) > 40, f"{key}: say why the merged codes need no telling apart"


def test_the_open_collapses_are_exactly_what_we_know_about() -> None:
    """`len(OPEN)` is the number this guard exists to make visible. It was 8 when the guard was built
    (2026-09-26) and 6 after the two EP-G4 fixes the same day. A fix or a ruling makes it go DOWN; a
    new finding arriving makes it go UP. Either is a deliberate edit here, never a silent drift."""
    assert len(OPEN) == 6


def test_a_site_is_never_in_both_registries() -> None:
    """The split is the point: a real gap must not be able to read as a design decision."""
    assert not (set(BY_DESIGN) & set(OPEN))


# ---------------------------------------------------------------- the gathering layer (impure)

_DECISION = '''
    A, B, C = "a", "b", "c"


    def decide(x):
        """Three states (pure — pinned)."""
        if x > 1:
            return A
        if x > 0:
            return "b"
        return C
'''


def _package(tmp_path, consumer: str, decision: str = _DECISION):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "dec.py").write_text(textwrap.dedent(decision))
    (pkg / "use.py").write_text(textwrap.dedent(consumer))
    return consumer_reads(str(pkg))


def _only(reads):
    assert len(reads) == 1, reads
    return reads[0]


def test_an_else_standing_for_one_code_distinguishes_it(tmp_path) -> None:
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide


            def show(x):
                code = decide(x)
                if code == "a":
                    return 1
                if code == "b":
                    return 2
                return 3
            """,
        )
    )
    assert read.codes == ("a", "b", "c")
    assert _disposition(read) == DISTINGUISHES_ALL


def test_the_terminal_standings_shape_is_a_collapse(tmp_path) -> None:
    """§3.2's historical instance: membership in a module constant that admits some codes, and a
    fall-through for the rest. The constant is read as its members."""
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide

            _TERMINAL = frozenset({"a"})


            def show(x):
                return 1 if decide(x) in _TERMINAL else 0
            """,
        )
    )
    assert read.distinguished == ("a",)
    assert _disposition(read) == COLLAPSES


def test_a_constant_imported_from_the_decisions_module_is_read_as_its_value(tmp_path) -> None:
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import A, C, decide


            def show(x):
                code = decide(x)
                if code == A:
                    return 1
                if code == C:
                    return 3
                return 2
            """,
        )
    )
    assert read.distinguished == ("a", "c")
    assert _disposition(read) == DISTINGUISHES_ALL


def test_truthiness_is_a_collapse_never_a_hand_off(tmp_path) -> None:
    """`if code:` and `bool(code)` tell no two non-empty codes apart."""
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide


            def show(x):
                code = decide(x)
                return 1 if code and bool(code) else 0
            """,
        )
    )
    assert read.forwards is False
    assert _disposition(read) == COLLAPSES


def test_a_code_that_flows_on_is_forwarded_not_judged(tmp_path) -> None:
    reads = _package(
        tmp_path,
        """
        from .dec import decide


        def returned(x):
            return decide(x)


        def rendered(x):
            print(f"state: {decide(x)}")


        def stored(x, out):
            out["state"] = decide(x)
        """,
    )
    assert [r.consumer for r in reads] == ["use.rendered", "use.returned", "use.stored"]
    assert {_disposition(r) for r in reads} == {FORWARDS}


def test_a_comparison_against_a_code_the_decision_never_returns_is_a_phantom(tmp_path) -> None:
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide


            def show(x):
                code = decide(x)
                if code == "a":
                    return 1
                if code == "renamed_away":
                    return 2
                return 3
            """,
        )
    )
    assert "renamed_away" in read.distinguished
    assert _disposition(read, "any reason at all, however long it is written") == PHANTOM_CODE


def test_an_alias_through_a_conditional_is_followed(tmp_path) -> None:
    """`named = code if ... else "x"` carries the code; comparisons on `named` count, and its extra
    literal is not mistaken for a phantom."""
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide


            def show(x):
                code = decide(x)
                named = code if code != "c" else "fallback"
                if named == "a":
                    return 1
                if named == "fallback":
                    return 3
                return 2
            """,
        )
    )
    assert read.distinguished == ("a", "c")
    assert _disposition(read) == DISTINGUISHES_ALL


def test_a_match_statement_names_its_cases(tmp_path) -> None:
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide


            def show(x):
                match decide(x):
                    case "a" | "b":
                        return 1
                    case _:
                        return 0
            """,
        )
    )
    assert read.distinguished == ("a", "b")
    assert _disposition(read) == DISTINGUISHES_ALL


def test_a_string_keyed_table_is_read_as_its_keys(tmp_path) -> None:
    read = _only(
        _package(
            tmp_path,
            """
            from .dec import decide

            _SAY = {"a": "first"}


            def show(x):
                return len(_SAY.get(decide(x), ""))
            """,
        )
    )
    assert read.distinguished == ("a",)
    assert _disposition(read) == COLLAPSES


def test_a_decision_with_an_open_code_set_is_outside_the_population(tmp_path) -> None:
    """A decision that can return something other than a known string is not guessed at."""
    reads = _package(
        tmp_path,
        """
        from .dec import decide


        def show(x):
            return 1 if decide(x) else 0
        """,
        decision='''
        def decide(x):
            """Not closed (pure — pinned)."""
            if x:
                return "a"
            return str(x)
        ''',
    )
    assert reads == []


def test_a_call_inside_a_nested_function_belongs_to_that_function(tmp_path) -> None:
    reads = _package(
        tmp_path,
        """
        from .dec import decide


        def outer(xs):
            def keep(x):
                return decide(x) != "a"

            return [x for x in xs if keep(x)]
        """,
    )
    assert [r.consumer for r in reads] == ["use.outer.keep"]
