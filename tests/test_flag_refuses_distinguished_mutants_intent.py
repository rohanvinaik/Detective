"""Intent: a mutant an execution on record distinguishes is never recorded, listed or offered as
"equivalent" (Detective #110, #113).

The defects, reproduced 2026-11-11 on Detective `ce2a500`:

* `detective flag … <id>` (default verdict `equivalent`) exited 0 and wrote `"verdict": "equivalent"`
  for a mutant the suite kills by crash (#110's `interval`/`SWAP_f9431aa0`); the next `audit` then
  listed it as `✓ flagged equivalent (your oracle — not gaps)`. `_run_flag` refused only divergence
  and timeout outcomes.
* A mutant the SUITE detects by crash, which the search cannot crash, stayed a candidate-equivalent
  and was offered to `flag`: the verdict carried `suite_detected`, but the partition read only the
  search's own crash witness. On #113's stand-in (`expr.py::attach`) audit listed six
  "unproven-equivalent" mutants, four of which carry `killed_by=crash`.
* audit passed the classifier no recalled `--input` while converge did, so the two verbs filed the
  same mutants in different classes (seventeen "unproven-equivalent" on audit; seven killable, six
  crash-only and four candidates on converge).

The ruling is KNOWABILITY §10: a witnessed execution resolves "equivalent or merely unobserved"
positively; a flag is a judgement and never outranks it. ARCHITECTURE §0: a crash kill pins the run,
not the value, an unspecified value-DOF and a different state from "candidate-equivalent". The old
deliberate invariant "a crash-killed mutant is flaggable" in `_run_flag` is NARROWED: it was true of
a mutant no execution tells apart, and false of every mutant a recorded one does.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

from Detective.cli import _FLAG_REFUSAL_REMEDY, equivalent_flag_admission
from Detective.engine import _detecting_test
from Detective.equivalence import (
    MutantVerdict,
    Witness,
    classify_survivor,
    distinction_clause,
    distinguishing_fact,
    verdict_distinction,
)
from Detective.equivalents import contract_disposition, contradicting_fact

# ------------------------------------------------------------------ the pure decisions


@pytest.mark.parametrize(
    ("killable", "crash_witness", "suite_detected", "expected"),
    [
        (False, False, False, "none"),
        (True, False, False, "value_witness"),
        (True, True, True, "value_witness"),  # a value witness outranks both crash facts
        (False, False, True, "suite_crash"),  # a test detects it; the search cannot crash it
        (False, True, True, "suite_crash"),  # both: the test is the fact a person can act on
        (False, True, False, "search_crash"),
    ],
)
def test_the_distinguishing_fact_is_one_named_code_over_the_three_recorded_facts(
    killable, crash_witness, suite_detected, expected
):
    assert distinguishing_fact(killable, crash_witness, suite_detected) == expected


@pytest.mark.parametrize(
    ("fact", "fence", "expected"),
    [
        ("none", False, "admit"),
        ("value_witness", False, "refuse_value_witness"),
        ("suite_crash", False, "refuse_suite_crash"),
        ("search_crash", False, "refuse_search_crash"),
        # A fence is a DIFFERENT claim (an authored must-not the suite does not enforce); it is true of
        # a crash-detected mutant whose value nothing pins, so it is never refused for that.
        ("suite_crash", True, "admit"),
        ("search_crash", True, "admit"),
        ("value_witness", True, "admit"),
        ("none", True, "admit"),
    ],
)
def test_flag_admission_refuses_only_the_equivalent_claim(fact, fence, expected):
    assert equivalent_flag_admission(fact, fence) == expected


def test_every_refusal_code_has_a_remedy_that_names_the_pin():
    for code in ("refuse_value_witness", "refuse_suite_crash", "refuse_search_crash"):
        assert "Pin" in _FLAG_REFUSAL_REMEDY[code] or "pin" in _FLAG_REFUSAL_REMEDY[code]
    assert "crash-only value gap" in _FLAG_REFUSAL_REMEDY["refuse_suite_crash"]
    assert "crash-only value gap" in _FLAG_REFUSAL_REMEDY["refuse_search_crash"]


@pytest.mark.parametrize(
    ("flag", "distinguished", "expected"),
    [
        ("equivalent", False, "equivalent"),
        ("equivalent", True, "contradicted"),
        ("fence", True, "fence"),
        ("fence", False, "fence"),
        ("", True, "candidate"),
        ("", False, "candidate"),
    ],
)
def test_an_equivalent_flag_is_contradicted_by_a_distinguishing_execution_not_a_fence(
    flag, distinguished, expected
):
    assert contract_disposition(True, False, False, flag, distinguished=distinguished) == expected


def test_a_witness_still_outranks_the_flag_and_a_budget_cut_is_not_a_contradiction():
    assert contract_disposition(True, True, False, "equivalent", distinguished=True) == "killable"
    assert (
        contract_disposition(True, False, False, "equivalent", diverged=True, distinguished=True)
        == "diverged"
    )
    assert contract_disposition(True, False, True, "equivalent", distinguished=True) == "unclassified"
    # The default keeps every existing caller's reading.
    assert contract_disposition(True, False, False, "equivalent") == "equivalent"


@pytest.mark.parametrize(
    ("flag", "fact", "expected"),
    [
        ("equivalent", "none", ""),
        ("equivalent", "value_witness", "value_witness"),
        ("equivalent", "suite_crash", "suite_crash"),
        ("equivalent", "search_crash", "search_crash"),
        ("fence", "suite_crash", ""),
        ("", "suite_crash", ""),
    ],
)
def test_only_an_equivalent_flag_can_be_contradicted(flag, fact, expected):
    assert contradicting_fact(flag, fact) == expected


def test_the_clause_names_the_test_or_the_input_and_never_invents_one():
    assert "tests/t.py::test_a" in distinction_clause("suite_crash", "tests/t.py::test_a", "")
    assert distinction_clause("suite_crash", "", "") == "a current test fails by crash under it"
    assert "f(3)" not in distinction_clause("search_crash", "", "")
    assert "(3)" in distinction_clause("search_crash", "", "3")
    assert "different value" in distinction_clause("value_witness", "", "")
    assert distinction_clause("none", "t", "3") == ""


def test_a_suite_detected_survivor_the_search_cannot_crash_leaves_the_candidate_class():
    """The partition consumes `suite_detected`: it is crash-only (not a candidate) with no input of
    the search's own, and it carries no invented witness."""

    def original(x):
        return x

    def mutant(x):
        return x  # the search finds no difference anywhere

    verdict = classify_survivor("M_1", "VALUE", "d", original, mutant, [(1,), (2,)], suite_detected=True)
    assert not verdict.killable
    assert verdict.crash_only is True
    assert verdict.crash_witness is None
    assert verdict.suite_detected is True
    assert verdict_distinction(verdict)[0] == "suite_crash"
    # The same mutant with no test on record is the one state that IS a candidate-equivalent.
    undetected = classify_survivor("M_1", "VALUE", "d", original, mutant, [(1,), (2,)], suite_detected=False)
    assert undetected.crash_only is False
    assert verdict_distinction(undetected)[0] == "none"


def test_a_search_crash_with_no_test_stays_crash_only_with_its_input():
    def original(x):
        return x

    def mutant(x):
        raise ValueError("boom")

    verdict = classify_survivor("M_2", "VALUE", "d", original, mutant, [(1,)], suite_detected=False)
    assert verdict.crash_only is True
    assert isinstance(verdict.crash_witness, Witness)
    assert verdict_distinction(verdict)[0] == "search_crash"
    assert "(1)" in verdict_distinction(verdict)[1]


def test_a_value_witness_is_killable_not_crash_only_even_when_a_test_detects_it():
    def original(x):
        return x

    def mutant(x):
        return x + 1

    verdict = classify_survivor("M_3", "VALUE", "d", original, mutant, [(1,)], suite_detected=True)
    assert verdict.killable and not verdict.crash_only


def test_the_detecting_test_is_the_sorted_first_of_the_matrix_by_either_key_spelling():
    matrix = {"M_1: replace x": ["b::t", "a::t"], "M_2: other": ["c::t"]}
    assert _detecting_test(matrix, {"mutant_id": "M_1", "mutant": "M_1: replace x"}) == "a::t"
    assert _detecting_test(matrix, {"mutant_id": "M_2", "mutant": "no such key"}) == "c::t"
    assert _detecting_test(matrix, {"mutant_id": "M_9", "mutant": "M_9: x"}) == ""
    assert _detecting_test({}, {"mutant_id": "M_1", "mutant": "M_1: replace x"}) == ""


def test_verdict_distinction_of_a_bare_verdict_is_none():
    assert verdict_distinction(MutantVerdict("M", "C", "d", False, None, 0)) == ("none", "")


# ------------------------------------------------------------------ live: the CLI on real projects

PYPROJECT = textwrap.dedent(
    """\
    [project]
    name = "fixture"
    version = "0"

    [tool.pytest.ini_options]
    pythonpath = ["."]
    testpaths = ["tests"]
    markers = ["detective: tests generated by Detective"]
    """
)

INTERVAL = textwrap.dedent(
    '''\
    def interval(text: str) -> int:
        """Seconds from 'every N', or -1 when the text is not one."""
        if not text.startswith("every ") or not text[6:].isdecimal():
            return -1
        seconds = int(text[6:])
        if seconds <= 0:
            return 0
        return seconds
    '''
)
INTERVAL_TEST = textwrap.dedent(
    """\
    import m


    def test_interval():
        assert m.interval("every 900") == 900
        assert m.interval("every 0") == 0
        assert m.interval("nope") == -1
    """
)

ATTACH = textwrap.dedent(
    '''\
    def attach(expr, inner):
        """Replace the one EVENT node under expr with an EVENT carrying inner."""
        matches = []

        def _search(node):
            if isinstance(node, tuple):
                if node[0] == "EVENT":
                    matches.append(node)
                for child in node[1:]:
                    _search(child)

        _search(expr)
        if len(matches) == 0:
            return expr, "none"
        if len(matches) > 1:
            return expr, "many"
        target = matches[0]

        def _replace(node):
            if node is target:
                return ("EVENT", inner)
            if isinstance(node, tuple):
                return tuple([node[0]] + [_replace(child) for child in node[1:]])
            return node

        return _replace(expr), "attached"
    '''
)
ATTACH_TEST = textwrap.dedent(
    """\
    from expr import attach


    def test_attach_replaces_the_single_event():
        tree = ("AND", ("EVENT", "a"), ("NOT", ("X", "b")))
        assert attach(tree, "z") == (("AND", ("EVENT", "z"), ("NOT", ("X", "b"))), "attached")


    def test_attach_reports_none():
        tree = ("AND", ("X", "a"))
        assert attach(tree, "z") == (tree, "none")


    def test_attach_reports_many():
        tree = ("AND", ("EVENT", "a"), ("EVENT", "b"))
        assert attach(tree, "z") == (tree, "many")


    def test_attach_keeps_leaves():
        tree = ("OR", "leaf", ("EVENT", "a"))
        assert attach(tree, "q") == (("OR", "leaf", ("EVENT", "q")), "attached")
    """
)

# The search reaches the crash at "k9" (a string constant it harvests) but NO test runs that branch.
UNREACHED = textwrap.dedent(
    """\
    def unreached(s):
        if s == "k9":
            return int(s[1:])
        return 0
    """
)
UNREACHED_TEST = textwrap.dedent(
    """\
    import unreached_mod


    def test_unreached():
        assert unreached_mod.unreached("zz") == 0
    """
)

# A mutant ONLY a recalled `--input` crashes: the guard is a sum no search derives, and the env read
# makes converge decline a golden, so the distinction stays uncaptured and audit must still see it.
GATED = textwrap.dedent(
    """\
    import os


    def gated(s):
        if sum(map(ord, s)) == 1234:
            return int(s[0:0] or "7") + len(os.environ.get("ZZ_NOPE_Q", ""))
        return 0
    """
)
GATED_TEST = textwrap.dedent(
    """\
    import gated_mod


    def test_gated():
        assert gated_mod.gated("zz") == 0
    """
)


def _project(tmp_path, name: str, source: str, test_source: str, module: str):
    project = tmp_path / name
    (project / "tests").mkdir(parents=True)
    (project / "pyproject.toml").write_text(PYPROJECT)
    (project / f"{module}.py").write_text(source)
    (project / "tests" / f"test_{module}.py").write_text(test_source)
    subprocess.run(["git", "init", "-q", str(project)], check=False)
    return project


def _cli(project, *args: str) -> subprocess.CompletedProcess:
    script = os.path.join(os.path.dirname(sys.executable), "detective")
    assert os.path.isfile(script), f"the installed console script is required beside {sys.executable}"
    env = {**os.environ, "HOME": str(project / ".home")}
    return subprocess.run(
        [script, *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=env,
    )


def _survivors(project, module: str, function: str) -> dict[str, dict]:
    """``{mutant_id: record}`` of the profile's value-survivors, read through the library."""
    code = (
        "import json,sys;from Detective.engine import profile;"
        f"r=profile({module + '.py'!r},{function!r},'.');"
        "print(json.dumps({x['mutant_id']:{'killed_by':x.get('killed_by'),'diff':x['diff_summary']} "
        "for x in r.value_survivor_records}))"
    )
    run = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env={**os.environ, "HOME": str(project / ".home")},
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


def _flags(project) -> dict:
    path = project / ".detective" / "equivalents.json"
    return json.loads(path.read_text()) if path.exists() else {}


# A mutant is named here by WHAT IT CHANGES, never by a literal id: a content id differs between
# Python 3.12 and 3.13+ (Wesker#48), so a literal pinned under one interpreter family names no mutant
# under the other. The first version of these tests used 3.14's literals and failed both 3.12 CI cells.
def _crash_detected(project) -> dict[str, dict]:
    """The survivors the suite detects by crash or exception, ``{mutant_id: record}``."""
    return {
        i: r
        for i, r in _survivors(project, "m", "interval").items()
        if r["killed_by"] in ("crash", "exception")
    }


def _int_dropped_id(project) -> str:
    """`seconds = int(text[6:])` -> `seconds = text[6:]`: #110's own mutant (3.14 spells it SWAP_f9431aa0).

    A diff summary is the original's lines after "- " then the mutant's after "+ "; only the mutant's
    half holds the changed line."""
    return next(
        i
        for i, r in _crash_detected(project).items()
        if "seconds = text[6:]" in r["diff"].split("\n+ ", 1)[-1]
    )


def _other_crash_detected_id(project) -> str:
    """A second crash-detected survivor, a VALUE mutant (3.14 spells it VALUE_138d2119)."""
    first = _int_dropped_id(project)
    return next(i for i in sorted(_crash_detected(project)) if i != first and i.startswith("VALUE_"))


def _assertion_killed_id(project) -> str:
    """A mutant the suite kills by assertion: it is not a survivor at all."""
    code = (
        "import json;from Detective.engine import profile;"
        "r=profile('m.py','interval','.');"
        "ids=sorted(x['mutant_id'] for x in r.killed_records if x.get('killed_by')=='assertion');"
        "print(json.dumps(ids))"
    )
    run = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env={**os.environ, "HOME": str(project / ".home")},
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])[0]


@pytest.fixture(scope="module")
def interval(tmp_path_factory):
    """#110's own fixture, converged once: the synthesized test crash-kills the `int(...)`-dropping mutant."""
    project = _project(tmp_path_factory.mktemp("interval"), "p", INTERVAL, INTERVAL_TEST, "m")
    run = _cli(project, "converge", "m.py::interval")
    assert "COMPLETE" in run.stdout, run.stdout + run.stderr
    return project


def test_flag_refuses_a_mutant_the_suite_detects_by_crash_and_writes_nothing(interval):
    before = _flags(interval)
    mutant_id = _int_dropped_id(interval)
    run = _cli(interval, "flag", "m.py::interval", mutant_id, "--note", "bogus")
    assert run.returncode == 1, run.stdout + run.stderr
    assert f"cannot flag mutant '{mutant_id}' as equivalent" in run.stderr
    assert "fails by crash under it" in run.stderr  # WHICH fact decides it
    assert "tests/" in run.stderr  # ... and which test
    assert "crash-only value gap" in run.stderr and "Pin the value" in run.stderr  # what to do instead
    assert "Nothing was recorded" in run.stderr
    assert "recorded" not in run.stdout
    assert _flags(interval) == before


def test_the_refusal_reaches_json_with_its_fact(interval):
    mutant_id = _other_crash_detected_id(interval)
    run = _cli(interval, "flag", "m.py::interval", mutant_id, "--json")
    payload = json.loads(run.stdout)
    assert run.returncode == 1
    assert (payload["verdict"], payload["reason"], payload["fact"]) == (
        "REFUSED",
        "distinguished_mutant",
        "suite_crash",
    )
    assert payload["mutant_id"] == mutant_id


def test_flag_refuses_the_same_mutant_under_two_sign(interval):
    before = _flags(interval)
    run = _cli(interval, "flag", "m.py::interval", _int_dropped_id(interval), "--two-sign")
    assert run.returncode == 1, run.stdout + run.stderr
    assert "cannot flag mutant" in run.stderr
    assert _flags(interval) == before, "a refusal writes nothing, whatever the store already holds"


def test_a_mutant_id_that_does_not_exist_is_refused_by_name(interval):
    run = _cli(interval, "flag", "m.py::interval", "SWAP_00000000")
    assert run.returncode == 1
    assert "no surviving mutant 'SWAP_00000000'" in run.stdout


def test_a_mutant_the_suite_kills_by_assertion_is_not_a_survivor_and_not_flaggable(interval):
    killed = _assertion_killed_id(interval)
    assert killed not in _survivors(interval, "m", "interval")
    run = _cli(interval, "flag", "m.py::interval", killed)
    assert run.returncode == 1
    assert f"no surviving mutant '{killed}'" in run.stdout


def test_a_genuinely_undistinguished_candidate_is_still_flaggable(interval):
    """`seconds <= 0` -> `seconds == 0`: `"-1".isdecimal()` is False, so no input reaches a negative
    count. This is the one state the equivalent flag is for, and it must still succeed."""
    survivors = _survivors(interval, "m", "interval")
    mutant_id = next(
        i for i, r in survivors.items() if "seconds == 0" in r["diff"] and "seconds <= 0" in r["diff"]
    )
    assert survivors[mutant_id]["killed_by"] in (None, "")
    run = _cli(interval, "flag", "m.py::interval", mutant_id, "--note", "isdecimal() excludes negatives")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "recorded" in run.stdout
    assert any(v["verdict"] == "equivalent" for v in _flags(interval).values())
    # ... and under --two-sign, the same claim on another candidate (the policy changes nothing here).
    other = next(
        i
        for i, r in survivors.items()
        if r["killed_by"] in (None, "") and i != mutant_id and "if False" in r["diff"]
    )
    two = _cli(interval, "flag", "m.py::interval", other, "--two-sign", "--note", "dead branch")
    assert two.returncode == 0, two.stdout + two.stderr


def test_a_fence_on_a_crash_detected_mutant_is_still_recorded_as_a_fence(interval):
    """The fence claims the opposite thing (an unenforced must-not): true of a mutant whose value no
    test pins, so it is kept. What it records: verdict `fence`, a GAP, never suppressed."""
    run = _cli(
        interval,
        "flag",
        "m.py::interval",
        _other_crash_detected_id(interval),
        "--fence",
        "--note",
        "pin the value",
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "fence — an unenforced must-not" in run.stdout
    assert any(v["verdict"] == "fence" for v in _flags(interval).values())


def test_an_old_equivalent_flag_is_contradicted_not_rendered_as_flagged_equivalent(interval):
    """A flag written before this rule (or by hand) on a crash-detected mutant: the store keeps it,
    the page says it is contradicted and by which test, and no count calls it flagged-equivalent."""
    survivors = _survivors(interval, "m", "interval")
    mutant_id = _int_dropped_id(interval)
    diff = survivors[mutant_id]["diff"]
    code = (
        "from Detective.engine import profile;from Detective.equivalents import add_flag;"
        "r=profile('m.py','interval','.');"
        f"rec=next(x for x in r.value_survivor_records if x['mutant_id']=={mutant_id!r});"
        "add_flag('.', r.function_key, rec['diff_summary'], note='legacy false flag')"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(interval),
        check=True,
        capture_output=True,
        env={**os.environ, "HOME": str(interval / ".home")},
    )
    assert any(v["diff"] == diff and v["verdict"] == "equivalent" for v in _flags(interval).values())
    run = _cli(interval, "audit", "m.py::interval")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "⚠ flag contradicted" in run.stdout and mutant_id in run.stdout
    assert "fails by crash under it" in run.stdout
    assert "kept on record, ignored" in run.stdout
    # The count of flagged-equivalents excludes it: the store holds one more `equivalent` flag than the
    # page counts, and the page's count is the genuine ones only.
    held = sum(1 for v in _flags(interval).values() if v["verdict"] == "equivalent")
    assert f"✓ flagged equivalent {held - 1} " in run.stdout, run.stdout
    conv = _cli(interval, "converge", "m.py::interval")
    assert "⚠ flag contradicted" in conv.stdout, conv.stdout
    # The flag record itself is not deleted.
    assert any(v["diff"] == diff and v["verdict"] == "equivalent" for v in _flags(interval).values())
    # And `flag` refuses to repeat the claim.
    again = _cli(interval, "flag", "m.py::interval", mutant_id)
    assert again.returncode == 1 and "cannot flag mutant" in again.stderr


def test_a_mutant_only_the_searchs_own_input_crashes_is_refused_by_that_input(tmp_path):
    project = _project(tmp_path, "p", UNREACHED, UNREACHED_TEST, "unreached_mod")
    survivors = _survivors(project, "unreached_mod", "unreached")
    mutant_id = next(i for i, r in survivors.items() if "s[0:0]" in r["diff"] or "int(s[0:" in r["diff"])
    assert survivors[mutant_id]["killed_by"] in (None, ""), "no current test may reach the branch"
    run = _cli(project, "flag", "unreached_mod.py::unreached", mutant_id)
    assert run.returncode == 1, run.stdout + run.stderr
    assert "makes it raise where the original returns" in run.stderr
    assert "'k9'" in run.stderr  # the input that decides it
    assert _flags(project) == {}
    fenced = _cli(project, "flag", "unreached_mod.py::unreached", mutant_id, "--fence")
    assert fenced.returncode == 0, fenced.stdout + fenced.stderr


@pytest.fixture(scope="module")
def attach(tmp_path_factory):
    return _project(tmp_path_factory.mktemp("attach"), "p", ATTACH, ATTACH_TEST, "expr")


def test_113_audit_does_not_call_suite_detected_mutants_unproven_equivalent(attach):
    survivors = _survivors(attach, "expr", "attach")
    detected = {i for i, r in survivors.items() if r["killed_by"] in ("crash", "exception")}
    assert len(detected) >= 4, "the stand-in must carry #113's suite-detected mutants"
    run = _cli(attach, "audit", "expr.py::attach", "--json")
    payload = json.loads(run.stdout)
    flaggable = set((payload["decision"].get("residual") or {}).get("flaggable_ids", []))
    assert not (flaggable & detected), "a suite-detected mutant is never offered to `flag`"
    page = _cli(attach, "audit", "expr.py::attach")
    assert "detected by" in page.stdout and "tests/test_expr.py::" in page.stdout, page.stdout
    # Its own % line counts them as killed (value+crash); the candidate count must agree. Of the twelve
    # non-killable survivors, ten have a recorded execution (four of them only a test's crash) and two
    # (`VALUE_2d7a15f5`, `VALUE_cb352827`) have none: before, six were "unproven-equivalent".
    unproven = next(ln for ln in page.stdout.splitlines() if "unproven-equiv" in ln and "survivor(s)" in ln)
    assert "2 survivor(s)" in unproven, page.stdout


def test_113_converge_and_the_decision_record_read_the_same_partition(attach):
    run = _cli(attach, "converge", "expr.py::attach", "--json")
    payload = json.loads(run.stdout)
    survivors = _survivors(attach, "expr", "attach")
    detected = {i for i, r in survivors.items() if r["killed_by"] in ("crash", "exception")}
    state = payload["decision"]["state"]
    assert detected <= set(state["crash_only"]), "suite-detected mutants are crash-only on converge"
    assert not (detected & set(state["candidate_equivalent"]))
    flaggable = set((payload["decision"].get("residual") or {}).get("flaggable_ids", []))
    assert flaggable == set(state["candidate_equivalent"])
    for verdict in payload["survivor_report"]["verdicts"]:
        if verdict["mutant_id"] in detected and not verdict["killable"]:
            assert verdict["crash_only"] is True and verdict["suite_detected"] is True
            assert verdict["detecting_test"].startswith(("tests/", "legacy:tests/"))
    _cli(attach, "converge", "expr.py::attach")  # the written report is the page's full form
    report = (attach / ".detective" / "reports" / "converge_attach.txt").read_text()
    assert "detected by crash: the test" in report


@pytest.fixture(scope="module")
def gated(tmp_path_factory):
    return _project(tmp_path_factory.mktemp("gated"), "p", GATED, GATED_TEST, "gated_mod")


def _classes(page: str) -> dict[str, int]:
    """The three class counts a page prints, from its terse rows."""
    counts = {"unproven": 0, "crash": 0, "killable": 0}
    for line in page.splitlines():
        words = line.split()
        if "unproven-equiv" in line and "survivor" in line or ("unproven-equiv" in line and "—" in line):
            counts["unproven"] = int(words[words.index("unproven-equiv") + 1])
        elif "crash-only-equiv" in line:
            counts["crash"] += int(words[words.index("crash-only-equiv") + 1])
        elif ("real gaps" in line or "still killable" in line) and "killable" in line:
            counts["killable"] = int(next(w for w in words if w.isdigit()))
    return counts


def test_audit_classifies_over_the_same_pool_converge_does(gated):
    """A recalled `--input` is part of the pool EVERY verb classifies over. Before: converge filed
    7 killable / 6 crash-only / 4 candidates and audit 17 unproven-equivalent, for the same verdicts."""
    conv = _cli(gated, "converge", "gated_mod.py::gated", "--input", "('aaaaaaaaaaaaF',)")
    aud = _cli(gated, "audit", "gated_mod.py::gated")
    assert _classes(aud.stdout) == _classes(conv.stdout), (conv.stdout, aud.stdout)
    assert _classes(aud.stdout)["killable"] > 0 and _classes(aud.stdout)["crash"] > 0
