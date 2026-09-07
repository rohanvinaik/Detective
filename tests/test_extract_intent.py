"""Intent tests for `detective extract` (Finding D, revalidation_2026-09-06.md).

survey DETECTS a pure decision trapped behind an impure boundary; decompose won't PERFORM it (its
seam is cognitive complexity, and it refuses a transform it cannot prove — which the impure function
is), so a greenfield author was left with no tool that acts. `extract` closes that gap propose-only.
These pin, from intent: extract and survey flag the IDENTICAL functions (they must never disagree —
the exact contradiction D found); a data-object param yields a concrete primitive-extraction proposal;
a heavy-import trap yields a MOVE proposal; and it writes nothing / proves nothing / has no --apply.
"""

from __future__ import annotations

from Detective.extract import (
    ExtractionProposal,
    extract_proposal,
    extract_readiness,
    render_extract,
)
from Detective.survey import survey_source

# ------------------------------------------------------------------ extract_readiness (the pure decision)


def test_readiness_names_each_case():
    assert extract_readiness("reachable", False) == "reachable"
    assert extract_readiness("extractable_core", True) == "propose"
    # Trapped, but no primitive found to key the decision on -> a hand extraction, not a signature.
    assert extract_readiness("extractable_core", False) == "no_primitive_seam"
    # A pure fn stranded only by its module's heavy imports -> a MOVE, not a sub-decision extraction.
    assert extract_readiness("trapped_by_imports", True) == "move"
    assert extract_readiness("trapped_by_imports", False) == "move"


# ------------------------------------------------------------------ extract <-> survey agreement (the D fix)

_CORE = "import numpy as np\n\ndef decide(grid: np.ndarray, k: int):\n    n = grid[0, 0]\n    return n + k\n"
_IMPORTS = (
    "from jax import numpy as jnp\n"
    "import argparse\n"
    "\n"
    "def str2bool(v):\n"
    "    if v.lower() in ('yes', 'true'):\n"
    "        return True\n"
    "    raise argparse.ArgumentTypeError('bad')\n"
)
_CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"


def test_extract_and_survey_flag_the_same_functions():
    # The load-bearing property: whatever survey flags, extract proposes on; whatever survey leaves
    # alone, extract returns None for. They must never contradict (Finding D was exactly a contradiction).
    for src in (_CORE, _IMPORTS, _CLEAN):
        flagged = {f.qualname for f in survey_source(src)}
        for name in ("decide", "str2bool", "add"):
            if f"def {name}" not in src:
                continue
            proposal = extract_proposal(src, name)
            assert (proposal is not None) == (name in flagged), (name, flagged)


def test_a_data_object_param_yields_a_primitive_extraction_proposal():
    p = extract_proposal(_CORE, "decide")
    assert p is not None
    assert p.disposition == "extractable_core"
    assert p.trapped_params == ("grid",)
    assert "n" in p.primitive_inputs  # n = grid[0, 0] is the primitive the decision reads
    assert extract_readiness(p.disposition, bool(p.primitive_inputs)) == "propose"


def test_a_heavy_import_trap_yields_a_move_proposal():
    p = extract_proposal(_IMPORTS, "str2bool")
    assert p is not None
    assert p.disposition == "trapped_by_imports"
    assert "jax" in p.heavy_imports
    assert extract_readiness(p.disposition, bool(p.primitive_inputs)) == "move"


def test_a_reachable_function_has_nothing_to_extract():
    assert extract_proposal(_CLEAN, "add") is None


# ------------------------------------------------------------------ render_extract (advisory, writes nothing)


def test_render_nothing_trapped_is_a_stated_clean_bill():
    out = "\n".join(render_extract("m.py", None))
    assert "nothing trapped" in out and "converge already reaches" in out


def test_render_propose_names_the_signature_and_the_converge_command():
    out = "\n".join(render_extract("game.py", extract_proposal(_CORE, "decide")))
    assert "def decide_decision(" in out
    assert "detective converge 'game.py::decide_decision'" in out
    # Advisory framing is always present — it proposes, never performs.
    assert "writes nothing and proves nothing" in out


def test_render_move_points_to_a_leaf_module_not_a_sub_decision():
    out = "\n".join(render_extract("utils.py", extract_proposal(_IMPORTS, "str2bool")))
    assert "trapped behind heavy module imports" in out
    assert "leaf module" in out
    assert "str2bool" in out


def test_the_proposal_is_a_frozen_advisory_record():
    # It is data, not an action — no apply path exists on it.
    p = extract_proposal(_CORE, "decide")
    assert isinstance(p, ExtractionProposal)
    assert not hasattr(p, "apply")
