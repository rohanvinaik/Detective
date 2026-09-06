"""Intent tests for `detective survey` — the pure-in-impure detector (docs/dogfood/pabkit_2026-09-06.md).

Written from intent, not from the code: what the survey MUST flag (a pure decision trapped behind an
impure boundary) and — the load-bearing half — what it must STAY QUIET on (aliased primitives,
Callable/Any params, functions that genuinely use the heavy stack), because a detector that cries
wolf is worse than none. The disclosed recall bound (an unannotated array param) is pinned too, so a
later "improvement" that starts flagging it trips this suite and gets a second look.
"""

from __future__ import annotations

from Detective.survey import (
    _annotation_inexpressible,
    render_survey,
    survey_disposition,
    survey_source,
)

# ------------------------------------------------------------------ survey_disposition (pure decision)


def test_disposition_names_each_block_most_blocking_first():
    assert survey_disposition(True, False, False) == "extractable_core"
    assert survey_disposition(False, True, False) == "impure_body"
    assert survey_disposition(False, False, True) == "trapped_by_imports"
    assert survey_disposition(False, False, False) == "reachable"


def test_an_inexpressible_param_outranks_the_other_blocks():
    # The param itself is the hardest block — extract the decision it wraps first.
    assert survey_disposition(True, True, True) == "extractable_core"


# ------------------------------------------------------------------ _annotation_inexpressible (denylist)


def test_known_data_objects_are_inexpressible():
    assert _annotation_inexpressible("np.ndarray") is True
    assert _annotation_inexpressible("ndarray") is True
    assert _annotation_inexpressible("torch.Tensor") is True
    assert _annotation_inexpressible("jnp.ndarray") is True


def test_primitives_aliases_callables_and_empties_are_not_flagged():
    # Precision: the denylist must NOT fire on primitives, on project aliases it cannot resolve, on a
    # bare Any/object (too broad — identity(x: Any) has nothing to extract), or on higher-order params.
    for annotation in (
        "int",
        "list[int]",
        "tuple[tuple[int]]",
        "Grid",
        "Numerical",
        "",
        "Any",
        "object",
        "Callable",
    ):
        assert _annotation_inexpressible(annotation) is False, annotation


# ------------------------------------------------------------------ survey_source (the scan)

_JAX_MODULE = (
    "from jax import numpy as jnp, vmap\n"
    "import argparse\n"
    "\n"
    "def str2bool(v):\n"  # pure, no jax reference -> trapped by the heavy import it does not use
    "    if v.lower() in ('yes', 'true'):\n"
    "        return True\n"
    "    raise argparse.ArgumentTypeError('bad')\n"
    "\n"
    "def smooth(ts):\n"  # references jnp -> genuinely uses the stack -> NOT flagged
    "    return jnp.ones(3) * ts\n"
)


def test_a_pure_fn_trapped_behind_a_heavy_import_it_does_not_use_is_flagged():
    findings = survey_source(_JAX_MODULE)
    flagged = {f.qualname: f.disposition for f in findings}
    assert flagged.get("str2bool") == "trapped_by_imports"


def test_a_fn_that_actually_uses_the_heavy_stack_is_not_flagged():
    findings = survey_source(_JAX_MODULE)
    assert "smooth" not in {f.qualname for f in findings}, "a genuine jnp user is not 'trapped'"


def test_an_ndarray_param_is_an_extractable_core():
    src = "import numpy as np\n\ndef decide(grid: np.ndarray, threshold: int):\n    return threshold\n"
    findings = survey_source(src)
    # `decide` references `np`? No — only the annotation does, not the body. The ndarray PARAM is the
    # block, so it is extractable_core, not trapped_by_imports.
    by_name = {f.qualname: f.disposition for f in findings}
    assert by_name.get("decide") == "extractable_core"


def test_no_false_positive_on_aliased_primitives_and_higher_order():
    # An arc-dsl-shaped module: type aliases + a Callable higher-order combinator, no heavy imports.
    src = (
        "from typing import Callable, Any\n"
        "Grid = tuple\n"
        "\n"
        "def add(a: 'Numerical', b: 'Numerical'):\n"
        "    return a\n"
        "\n"
        "def apply(f: Callable, c: Any):\n"
        "    return f(c)\n"
    )
    assert survey_source(src) == [], "aliases / Callable / Any must not be flagged"


def test_an_unannotated_array_param_is_now_caught_by_usage_inference():
    # GofL Game.update_cell shape: `step` is unannotated, but `step[xy[0], xy[1]]` — a tuple subscript
    # no list/str/dict accepts — types it as ndarray via USAGE inference. This DELIBERATELY flips the
    # old recall-gap silence: the survey now flags it. The old test pinned the silence precisely so
    # this flip had to be a conscious decision (the type-inference work, step 2), not a drift.
    src = "def update_cell(step, xy):\n    return step[xy[0], xy[1]]\n"
    by_name = {f.qualname: f.disposition for f in survey_source(src)}
    assert by_name.get("update_cell") == "extractable_core"


def test_the_recall_bound_narrows_but_does_not_vanish():
    # Usage inference emits only HIGH-confidence types, so an unannotated param with AMBIGUOUS usage
    # (a plain subscript could be list/dict/ndarray; arithmetic could be int/ndarray) is STILL not
    # flagged — the survey does not guess. The recall bound narrowed; it did not disappear.
    src = "def f(xs):\n    return xs[0] + 1\n"
    assert survey_source(src) == []


# ------------------------------------------------------------------ render_survey


def test_render_says_nothing_trapped_on_a_clean_file():
    out = "\n".join(render_survey("m.py", []))
    assert "0 trapped" in out and "nothing trapped" in out


def test_render_lists_findings_with_the_extraction_and_the_recall_bound():
    findings = survey_source(_JAX_MODULE)
    out = "\n".join(render_survey("m.py", findings))
    assert "str2bool" in out
    assert "trapped_by_imports" in out
    assert "Recall bound" in out  # the limitation is always disclosed, never a clean bill
