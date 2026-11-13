"""Intent: sibling verdict-cache rows coexist, and a test a converge wrote fingerprints the same in the
next session, so a bare re-run hits the cache (#100).

THE DEFECT (Detective #100, re-measured 2026-10-26):

1. `verdict_cache.params_suffix` took the last `_PARAM_FIELDS = 3` fields of a key. The key grew optional
   tail fields (`:defer_shaped`, `:two_sign`, the regime digest), so the "suffix" wandered. A default
   converge's suffix had no pass field at all (`{budgets}:defer_shaped:{regime}`) and a two-sign one ended
   `{budgets}:two_sign:{regime}`: every pass evicted the others, a two-sign `put` evicted the one-sign
   row, and a fast pass evicted the comprehensive one. A two-pass converge's final measurement missed the
   row pass 0 had just stored.
2. A test a converge WROTE fingerprinted differently from the same file collected by the next session
   (run 1's final put used tests hash X over the written `*_synth.py`, run 2 hashed identical bytes to Y).
   MECHANISM, found by diffing the inputs of `Wesker.trace_cache.test_fingerprint` in the two sessions:
   (a) the node id: a test the run wrote after the session collected is re-collected as a bare callable
   named `test_grade_boundary_0`, while the next session's live item carries `tests/detective/..::
   test_grade_boundary_0`; (b) the fixture-definition files: a live item stamps pytest's own
   `_pytest/python.py` for its fixture closure, a re-collected callable stamps none. Source, origin file
   and conftest digests were identical.

THE FIX: a row's question is read by NAME (`key_question`), and each test is put in a canonical form
(`canonical_test_identity`, `fixture_origin_scope`) before it is fingerprinted.
"""

from __future__ import annotations

import json

import pytest
from Wesker.engine import ProfilingResult

from Detective import verdict_cache
from Detective.verdict_cache import (
    cache_key,
    canonical_test_identity,
    fixture_origin_scope,
    key_prefix,
    key_question,
    tests_fingerprint,
)

_FN = "m.py::f"
_PREFIX = key_prefix(_FN)


def _key(source="def f(): pass", **over):
    args = dict(
        func_key=_FN,
        func_source=source,
        tests=[],
        max_per_category=0,
        pass_index=0,
        trace_budgets=(50.0, 1800.0),
    )
    args.update(over)
    return cache_key(**args)


def _put(root, key):
    verdict_cache.put(str(root), key, _PREFIX, ProfilingResult(function_key=_FN))


def _served(root, key):
    return verdict_cache.get(str(root), key) is not None


# ── the question a row answers is read by name ────────────────────────────────────────────────────


def test_a_question_is_the_named_parameters_and_not_the_engine_source_or_tests():
    base = key_question(_key(), _PREFIX)
    assert base == "max=0;pass=0;budgets=50,1800;shaped=full;sign=one;regime="
    # another source or another engine answers the SAME question at a different time
    assert key_question(_key(source="def f(): return 1"), _PREFIX) == base
    # each named parameter separates questions
    assert key_question(_key(max_per_category=5), _PREFIX) != base  # fast vs comprehensive
    assert key_question(_key(pass_index=1), _PREFIX) != base  # one pass vs the next
    assert key_question(_key(trace_budgets=(None, None)), _PREFIX) != base
    assert key_question(_key(full_matrix=True), _PREFIX) != base
    assert key_question(_key(include_shaped=False), _PREFIX) != base  # deferred vs shaped
    assert key_question(_key(two_sign=True), _PREFIX) != base  # two-sign vs one-sign
    assert key_question(_key(regime_digest="abc123"), _PREFIX) != base


def test_the_optional_tail_is_read_marker_by_marker_in_the_order_the_builder_writes_it():
    both = key_question(_key(include_shaped=False, two_sign=True, regime_digest="r1"), _PREFIX)
    assert both.endswith("shaped=defer;sign=two;regime=r1")
    assert key_question(_key(include_shaped=False, regime_digest="r1"), _PREFIX).endswith(
        "shaped=defer;sign=one;regime=r1"
    )
    assert key_question(_key(two_sign=True), _PREFIX).endswith("shaped=full;sign=two;regime=")


@pytest.mark.parametrize(
    "key",
    [
        "",
        "other.py::g:e:s:t:0:0:50,1800",  # outside the prefix
        f"{_PREFIX}e:s:t:0:0",  # an older layout: no budgets field
        f"{_PREFIX}e:s:t:0:0:nobudgets",  # a budgets field without its two parts
        f"{_PREFIX}e:s:t:0:0:50,1800:one:two:three",  # more tail than the layout has
    ],
)
def test_a_key_the_current_layout_cannot_parse_is_a_fossil_with_no_question(key):
    assert key_question(key, _PREFIX) == ""


def test_an_empty_prefix_names_no_question():
    assert key_question(_key(), "") == ""


# ── eviction keeps siblings and drops only stale copies of one question ───────────────────────────


def test_two_passes_of_a_two_sign_converge_coexist_and_both_are_served(tmp_path):
    """Counter-test 1: pass 1's put used to evict pass 0's row, so a final measurement missed the cache
    right after pass 0 stored it."""
    for shaped in (True, False):
        zero = _key(source="s0", pass_index=0, two_sign=True, include_shaped=shaped, regime_digest="r")
        one = _key(source="s0", pass_index=1, two_sign=True, include_shaped=shaped, regime_digest="r")
        _put(tmp_path, zero)
        _put(tmp_path, one)
        assert _served(tmp_path, zero) and _served(tmp_path, one)


def test_a_fast_run_leaves_the_comprehensive_row_in_place(tmp_path):
    """Counter-test 2: a `--fast` sample is a different question from the comprehensive run."""
    for shaped in (True, False):  # a converge defers shaped tests, which hid max/pass from the suffix
        comprehensive = _key(max_per_category=0, include_shaped=shaped)
        _put(tmp_path, comprehensive)
        _put(tmp_path, _key(max_per_category=5, include_shaped=shaped))
        assert _served(tmp_path, comprehensive)


def test_a_two_sign_put_leaves_the_one_sign_row_and_the_reverse(tmp_path):
    one_sign = _key(include_shaped=False, regime_digest="r")
    two_sign = _key(include_shaped=False, two_sign=True, regime_digest="r")
    _put(tmp_path, one_sign)
    _put(tmp_path, two_sign)
    assert _served(tmp_path, one_sign) and _served(tmp_path, two_sign)
    _put(tmp_path, one_sign)
    assert _served(tmp_path, two_sign)


def test_a_deferred_run_and_a_shaped_run_coexist_and_so_do_two_regimes(tmp_path):
    keys = [
        _key(include_shaped=False),
        _key(include_shaped=True),
        _key(regime_digest="r1"),
        _key(regime_digest="r2"),
        _key(full_matrix=True),
    ]
    for key in keys:
        _put(tmp_path, key)
    assert all(_served(tmp_path, key) for key in keys)


def test_a_stale_copy_of_the_same_question_is_still_evicted(tmp_path):
    """Single-valid-copy survives: an edit to the function answers the same question under a new hash."""
    old = _key(source="def f(): pass", two_sign=True, include_shaped=False, regime_digest="r")
    new = _key(source="def f(): return 1", two_sign=True, include_shaped=False, regime_digest="r")
    _put(tmp_path, old)
    _put(tmp_path, new)
    assert _served(tmp_path, new) and not _served(tmp_path, old)


def test_a_fossil_of_an_older_layout_is_evicted_and_another_functions_row_is_untouched(tmp_path):
    fossil = f"{_PREFIX}e:s:t:0:0"  # fewer fields than any current key
    other = "other.py::g:e:s:t:0:0:50,1800"
    cache_path = tmp_path / ".detective" / "verdict_cache.json"
    cache_path.parent.mkdir()
    entry = verdict_cache._to_json(ProfilingResult(function_key=_FN))
    cache_path.write_text(json.dumps({fossil: entry, other: entry}))
    _put(tmp_path, _key())
    rows = json.loads(cache_path.read_text())
    assert fossil not in rows and other in rows and _key() in rows


# ── a test fingerprints the same whichever route collected it (#100 item 2) ─────────────────────


@pytest.mark.parametrize(
    ("node_id", "origin", "identity"),
    [
        ("tests/t.py::test_x", "/p/tests/t.py", "/p/tests/t.py::test_x"),  # a live item
        ("test_x", "/p/tests/t.py", "/p/tests/t.py::test_x"),  # the same test, re-collected bare
        ("tests/t.py::TestC::test_x[a-1]", "/p/tests/t.py", "/p/tests/t.py::TestC::test_x[a-1]"),
        ("test_x", "", "test_x"),  # no file known: the id as it is
        ("", "/p/tests/t.py", "/p/tests/t.py::"),
    ],
)
def test_the_identity_is_the_file_and_the_member_path_inside_it(node_id, origin, identity):
    assert canonical_test_identity(node_id, origin) == identity


@pytest.mark.parametrize(
    ("path", "scope"),
    [
        ("/usr/lib/python3.14/site-packages/_pytest/python.py", "installed"),
        ("/usr/lib/python3.14/site-packages", "installed"),
        ("/usr/lib/python3.14/site-packages-extra/x.py", "project"),  # a sibling name, not a child
        ("/p/tests/conftest.py", "project"),
        ("", "project"),
    ],
)
def test_only_installed_package_fixtures_are_left_out_of_a_tests_fingerprint(path, scope):
    assert fixture_origin_scope(path, ["/usr/lib/python3.14/site-packages", ""]) == scope


def _callable(name, origin, fixtures=()):
    def run():  # a stand-in for a collected test
        return None

    run.__name__ = run.__qualname__ = name
    run.__wesker_origin__ = str(origin)
    run.__wesker_fixture_origins__ = tuple(str(f) for f in fixtures)
    return run


def test_a_live_item_and_the_same_test_re_collected_bare_fingerprint_alike(tmp_path):
    """The mechanism of the written test's second-session miss: same source and file, different
    node-id spelling and un-stamped installed-package fixtures."""
    import _pytest.python

    test_file = tmp_path / "test_m.py"
    test_file.write_text("def test_x():\n    assert True\n")
    live = _callable("tests/test_m.py::test_x", test_file, fixtures=[_pytest.python.__file__])
    recollected = _callable("test_x", test_file)
    assert tests_fingerprint([live]) == tests_fingerprint([recollected])


def test_a_project_fixture_edit_and_a_test_file_edit_still_change_the_fingerprint(tmp_path):
    test_file = tmp_path / "test_m.py"
    test_file.write_text("def test_x():\n    assert True\n")
    fixture_file = tmp_path / "fixtures_extra.py"
    fixture_file.write_text("VALUE = 1\n")
    item = _callable("test_x", test_file, fixtures=[fixture_file])
    before = tests_fingerprint([item])
    fixture_file.write_text("VALUE = 2\n")
    after_fixture = tests_fingerprint([item])
    test_file.write_text("def test_x():\n    assert False\n")
    after_test = tests_fingerprint([item])
    assert len({before, after_fixture, after_test}) == 3


def test_two_different_tests_in_one_file_still_fingerprint_apart(tmp_path):
    test_file = tmp_path / "test_m.py"
    test_file.write_text("def test_x():\n    pass\n\n\ndef test_y():\n    pass\n")
    assert tests_fingerprint([_callable("test_x", test_file)]) != tests_fingerprint(
        [_callable("test_y", test_file)]
    )
