"""Native tests for Detective.decompose — the docstring-preservation invariant.

``find_extraction_candidates`` takes an ``ast.FunctionDef``, which converge cannot
synthesize as ``--input`` (an AST node is not literal-eval'able), so this engine-core
behavior is guarded by a unit suite — the sanctioned exemption to the converge-generate
discipline (mirrors test_capture_native.py). The invariant pinned here: a function's
leading docstring belongs to the FUNCTION and is never swept into an extracted helper
(which would both mis-describe the helper and strip the parent of its own docstring).
"""

from __future__ import annotations

import ast
import textwrap

import pytest

from Detective.decompose import _suggest_name, find_extraction_candidates
from Detective.decompose_apply import extract_candidate

_SRC = '''\
def f(a, b, c):
    """A function docstring that must stay with f."""
    base = a * 2
    if a > 10:
        x = 1
    elif a > 5:
        x = 2
    else:
        x = 3
    if b:
        x += c
    total = x + base
    return total
'''


def _funcdef(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_no_candidate_block_starts_at_the_docstring():
    cands = find_extraction_candidates(_funcdef(_SRC))
    assert cands  # there is a genuinely extractable block
    # the docstring is line 2; a block must never begin there (or earlier)
    assert all(c.start_line > 2 for c in cands)


def test_extraction_leaves_docstring_with_parent_not_helper():
    cands = find_extraction_candidates(_funcdef(_SRC))
    ex = extract_candidate(_SRC, "f", cands[0])
    assert ex is not None
    ns = ex.new_source
    # the docstring survives exactly once, and belongs to f (which is spliced AFTER the
    # helper), never to the helper that comes first in the rewritten source
    assert ns.count('"""A function docstring') == 1
    assert ns.index('"""A function docstring') > ns.index("def f(")
    helper_part = ns[: ns.index("def f(")]
    assert '"""' not in helper_part


def test_docstringless_function_still_decomposes():
    # the docstring-skip path must not regress ordinary extraction
    src = _SRC.replace('    """A function docstring that must stay with f."""\n', "")
    assert find_extraction_candidates(_funcdef(src))


# ── issue #2 / #3: seam placement and helper naming ─────────────────────────────
# Black-box finding: on this fixture the boundary landed one statement past the
# real seam, swallowing `out = []` — the helper returned a freshly-constructed
# empty container — and was named `_compute_name` after a loop-local it does not
# return. The seam is the aggregation; the initializer belongs to its consumer.

_TALLY_SRC = """\
def summarize(rows):
    totals = {}
    for r in rows:
        name = r.get("name") or "unknown"
        v = r.get("value", 0)
        if v < 0:
            v = 0
        totals[name] = totals.get(name, 0) + v

    out = []
    for key in sorted(totals):
        t = totals[key]
        if t == 0:
            continue
        label = key.upper() if t > 100 else key
        out.append(f"{label}={t}")
    return ", ".join(out)
"""


def test_trailing_empty_initializer_is_retracted_not_swallowed():
    cands = find_extraction_candidates(_funcdef(_TALLY_SRC))
    assert cands  # the aggregation seam must survive retraction
    top = cands[0]
    # the block stops at the aggregation loop; `out = []` (line 10) stays with its consumer
    assert top.end_line < 10
    assert top.outputs == ("totals",)
    assert "out" not in top.outputs


def test_helper_is_named_after_what_it_returns():
    cands = find_extraction_candidates(_funcdef(_TALLY_SRC))
    assert cands[0].proposed_name == "_compute_totals"


def test_retracted_extraction_runs_green():
    ns_orig: dict = {}
    exec(compile(_TALLY_SRC, "<orig>", "exec"), ns_orig)
    cases = [
        [{"name": "a", "value": 5}],
        [{"name": "b", "value": 150}],
        [{"name": "c", "value": -3}],
        [],
    ]
    expected = [ns_orig["summarize"](rows) for rows in cases]
    for cand in find_extraction_candidates(_funcdef(_TALLY_SRC)):
        ex = extract_candidate(_TALLY_SRC, "summarize", cand)
        if ex is None:
            continue
        ns: dict = {}
        exec(compile(ex.new_source, "<rewritten>", "exec"), ns)
        assert [ns["summarize"](rows) for rows in cases] == expected



def test_extract_from_annotated_function_types_def_bare_call_and_keeps_comment():
    """Applying a split to an ANNOTATED function must (a) type the helper's DEF from the parent's
    params (#28), (b) keep the CALL bare — a typed call site is a SyntaxError that broke a target
    repo's build on every applied split — and (c) not strand/drop a comment inside the moved block
    (#29). The pre-existing fixtures are unannotated, which hid the typed-call regression."""
    src = (
        "def summarize(rows: list[dict], cap: int) -> str:\n"
        "    totals: dict = {}\n"
        "    for r in rows:\n"
        "        name = r.get('name') or 'unknown'\n"
        "        v = r.get('value', 0)\n"
        "        if v < 0:\n"
        "            v = 0\n"
        "        totals[name] = totals.get(name, 0) + v\n"
        "        # clamp negatives before tallying\n"
        "\n"
        "    out = []\n"
        "    for key in sorted(totals):\n"
        "        t = totals[key]\n"
        "        if t == 0:\n"
        "            continue\n"
        "        label = key.upper() if t > cap else key\n"
        "        out.append(f'{label}={t}')\n"
        "    return ', '.join(out)\n"
    )
    cands = find_extraction_candidates(_funcdef(src))
    assert cands, "the annotated fixture should offer an extraction"
    ext = extract_candidate(src, "summarize", cands[0])
    assert ext is not None
    ast.parse(ext.new_source)  # valid Python — a typed call site would raise here
    lines = ext.new_source.splitlines()
    defsig = next(line for line in lines if line.startswith(f"def {ext.helper_name}("))
    callln = next(line for line in lines if f"{ext.helper_name}(" in line and not line.lstrip().startswith("def "))
    assert ": " in defsig.split("(", 1)[1], f"def should carry parent annotations: {defsig}"
    assert ": " not in callln.split("(", 1)[1], f"call must be bare: {callln}"
    assert "# clamp negatives before tallying" in ext.new_source  # comment preserved, not dropped


@pytest.mark.parametrize(
    "src, expected",
    [
        ("x = []", True),
        ("x = {}", True),
        ("x = ()", True),
        ("x = set()", True),
        ("x = frozenset()", True),
        ("x = list()", True),
        ("x = dict()", True),
        ("x = tuple()", True),
        ("x = ''", True),
        ("x = 0", True),
        ("x = 0.0", True),
        ("x = b''", True),
        ("x = False", False),  # a bool is a flag, not an empty accumulator
        ("x = [1]", False),
        ("x = {'k': 1}", False),
        ("x = set(rows)", False),
        ("x = 'a'", False),
        ("x = 1", False),
        ("x, y = [], []", False),  # multi-target: not the observed initializer shape
        ("x[0] = []", False),  # subscript store mutates, binds nothing
        ("x += []", False),
        ("x = f()", False),
    ],
)
def test_empty_initializer_grid(src, expected):
    stmt = ast.parse(src).body[0]
    from Detective.decompose import _is_empty_initializer

    assert _is_empty_initializer(stmt) is expected


def test_two_statement_seam_is_enumerated_by_default():
    # Review finding 5: an initializer + accumulator loop is a real seam at width 2
    src = """\
def f(rows):
    total = 0
    for r in rows:
        if r > 0:
            total += r
    label = "big" if total > 100 else "small"
    return f"{label}:{total}"
"""
    cands = find_extraction_candidates(_funcdef(src))
    assert any(c.start_line == 2 and c.end_line == 5 for c in cands)


def test_helper_name_never_collides_with_module_symbols():
    # Review finding 5: an existing module-level `_compute_totals` must be reserved
    src = "def _compute_totals():\n    return 1\n\n\n" + _TALLY_SRC
    summarize = ast.parse(src).body[1]
    assert isinstance(summarize, ast.FunctionDef)
    cands = find_extraction_candidates(summarize)
    assert cands and cands[0].proposed_name == "_compute_totals"
    ex = extract_candidate(src, "summarize", cands[0])
    assert ex is not None
    assert ex.helper_name == "_compute_totals_2"
    ns: dict = {}
    exec(compile(ex.new_source, "<rewritten>", "exec"), ns)
    assert ns["_compute_totals"]() == 1  # the pre-existing symbol is untouched
    assert ns["summarize"]([{"name": "a", "value": 5}]) == "a=5"


# ── _suggest_name: behavioral-signature templates ────────────────────────
def _stmts(src: str):
    return ast.parse(textwrap.dedent(src)).body


def test_suggest_name_single_meaningful_output_keeps_compute_form():
    # A single, descriptive output still names the helper for what it returns.
    assert _suggest_name({"totals"}, "abc") == "_compute_totals"


def test_suggest_name_generic_or_multi_output_does_not_concatenate():
    # Issue #26: never dress a throwaway name or a return TUPLE up as a purpose. A single
    # signal-free output (`x`, `out`, `result`) and 2+ outputs both fall to the honest bland
    # parent-derived form for the human to rename — not `_compute_x` / `_compute_fee_total`.
    assert _suggest_name({"x"}, "abc") == "_abc_helper"
    assert _suggest_name({"out"}, "abc") == "_abc_helper"
    assert _suggest_name({"total", "fee"}, "process_row") == "_process_row_helper"
    # An already-underscored parent must not double up into a name-mangling `__` prefix.
    assert _suggest_name({"a", "b"}, "_conjunction_sentences") == "_conjunction_sentences_helper"


def test_suggest_name_raise_only_block_is_a_validator():
    block = _stmts("""
        if not items:
            raise ValueError("no items")
        if region not in ("us", "ca"):
            raise ValueError("bad region")
    """)
    assert _suggest_name(set(), "process_order", block) == "_validate_order_inputs"


def test_suggest_name_validator_from_single_token_parent():
    block = _stmts("""
        if x < 0:
            raise ValueError("bad")
    """)
    assert _suggest_name(set(), "handle", block) == "_validate_inputs"


def test_suggest_name_void_block_without_raise_keeps_fallback():
    block = _stmts("y = sink(1)")
    assert _suggest_name(set(), "process_order", block) == "_process_order_helper"


def test_suggest_name_boolean_output_gets_predicate_form():
    block = _stmts("""
        valid = a < b and c == d
        if e:
            valid = False
    """)
    assert _suggest_name({"valid"}, "check", block) == "_is_valid"


def test_suggest_name_existing_predicate_prefix_not_doubled():
    block = _stmts("is_ready = count > 0")
    assert _suggest_name({"is_ready"}, "poll", block) == "_is_ready"


def test_suggest_name_non_boolean_assignment_disqualifies_predicate():
    block = _stmts("""
        flag = a < b
        flag = count + 1
    """)
    assert _suggest_name({"flag"}, "check", block) == "_compute_flag"


def test_suggest_name_output_never_assigned_in_block_is_not_vacuously_boolean():
    block = _stmts("other = 1")
    assert _suggest_name({"flag"}, "check", block) == "_compute_flag"


def test_suggest_name_underscored_outputs_are_ignored_for_naming():
    block = _stmts("""
        if x:
            raise ValueError("bad")
    """)
    assert _suggest_name({"_tmp"}, "process_order", block) == "_validate_order_inputs"


def test_suggest_name_negation_is_boolean_shaped():
    block = _stmts("idle = not busy")
    assert _suggest_name({"idle"}, "check", block) == "_is_idle"


def test_suggest_name_non_not_unary_is_not_boolean_shaped():
    block = _stmts("delta = -offset")
    assert _suggest_name({"delta"}, "check", block) == "_compute_delta"


def test_assigns_only_boolean_walks_into_compound_statements():
    from Detective.decompose import _assigns_only_boolean

    # a non-boolean assignment hiding inside a For disqualifies…
    block = _stmts("""
        total = a < b
        for i in items:
            total = i + 1
    """)
    assert _assigns_only_boolean("total", block) is False
    # …while boolean-shaped assignments inside compounds still qualify
    block2 = _stmts("""
        count = 0
        for i in items:
            ok = i > 0
    """)
    assert _assigns_only_boolean("ok", block2) is True


def test_assigns_only_boolean_int_constant_is_not_boolean_shaped():
    from Detective.decompose import _assigns_only_boolean

    # 0 is falsy but not False-the-bool: a plain int constant disqualifies
    assert _assigns_only_boolean("done", _stmts("done = 0")) is False
    assert _assigns_only_boolean("done", _stmts("done = True")) is True
