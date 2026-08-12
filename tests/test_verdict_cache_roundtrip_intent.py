"""#6b — a replayed verdict must be the measured one, TRACE EVIDENCE included.

The defect: ``_to_json`` uses ``dataclasses.asdict`` (recursive), which flattens the one nested
dataclass field ``asdict`` reaches beyond ``per_category`` — ``trace_evidence: tuple[TraceEvidence,
...]`` — to a list of plain dicts, and its ``lines`` / ``arcs`` tuples to lists. ``_from_json``
rebuilt only ``CategoryResult``, so a WARM result carried ``dict`` trace rows. Nothing raised on the
read: the break surfaced only downstream, when a consumer touched ``admissible_arc_union`` /
``admissible_union`` / ``observed_union`` — the exact signals #59/#17 rest the proof basis on —
and got ``AttributeError: 'dict' object has no attribute 'admissible'`` (or a ``TypeError`` from
set-building over list-of-lists arcs). A verdict cache whose whole claim is "the replay IS the
measurement" silently served a result that could not answer its own admissibility question.

These are INTENT tests (a characterization of current output could not catch a warm/cold DISAGREEMENT
— it would pin the disagreement). They assert the round-trip is faithful through the real ``put`` /
``get`` path, and each fails without the ``trace_evidence`` reconstruction + tuple retyping in
``_from_json``.
"""

from __future__ import annotations

import json
import os
import sys

from Wesker.trace_evidence import TraceEvidence

from Detective import verdict_cache
from Detective.engine import profile


def _profiled(tmp_path):
    """A real ProfilingResult with two trace-evidence owners (one green, one failing)."""
    (tmp_path / "choo.py").write_text("def choose(flag):\n    if flag:\n        return 1\n    return 0\n")
    (tmp_path / "test_choo.py").write_text(
        "from choo import choose\n\n\n"
        "def test_green():\n    assert choose(True) == 1\n\n\n"
        "def test_failing_only():\n    assert choose(False) == 1\n"
    )
    for name in ("choo", "test_choo"):
        sys.modules.pop(name, None)
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        return profile("choo.py", "choose", str(tmp_path))
    finally:
        os.chdir(cwd)


def test_warm_trace_evidence_reconstructs_to_the_dataclass(tmp_path):
    """After a round-trip the trace rows are ``TraceEvidence`` again, not the dicts ``asdict`` made."""
    cold = _profiled(tmp_path)
    assert cold.trace_evidence, "fixture must produce trace evidence, else the test proves nothing"
    warm = verdict_cache._from_json(json.loads(json.dumps(verdict_cache._to_json(cold))))
    assert all(isinstance(ev, TraceEvidence) for ev in warm.trace_evidence)


def test_warm_admissibility_unions_match_cold_and_do_not_raise(tmp_path):
    """The proof-basis signals (#59/#17) survive the cache: warm equals cold on all three unions,
    where before the fix each raised on the ``dict`` trace rows."""
    cold = _profiled(tmp_path)
    warm = verdict_cache._from_json(json.loads(json.dumps(verdict_cache._to_json(cold))))
    for prop in ("admissible_arc_union", "admissible_union", "observed_union"):
        assert getattr(warm, prop) == getattr(cold, prop), prop


def test_tuple_typed_fields_keep_their_declared_type(tmp_path):
    """``json`` degrades ``collection_conflicts`` / ``proof_basis`` tuples to lists; a warm value must
    hash and compare like the cold one it replays, so the declared tuple type is restored."""
    cold = _profiled(tmp_path)
    warm = verdict_cache._from_json(json.loads(json.dumps(verdict_cache._to_json(cold))))
    assert isinstance(warm.collection_conflicts, tuple)
    assert isinstance(warm.proof_basis, tuple)
    assert warm.collection_conflicts == cold.collection_conflicts
    assert warm.proof_basis == cold.proof_basis


def test_end_to_end_through_the_real_put_get_path(tmp_path):
    """The whole point: a hit off the real ``put`` / ``get`` file path can answer its own
    admissibility question. Before the fix this ``get`` succeeded and the union access below crashed."""
    cold = _profiled(tmp_path)
    root = str(tmp_path)
    key = "verdict::choo.py::choose:abc:def:0"
    prefix = "verdict::choo.py::choose:"
    verdict_cache.put(root, key, prefix, cold)
    hit = verdict_cache.get(root, key)
    assert hit is not None
    assert getattr(hit, "served_from_cache", False) is True
    assert all(isinstance(ev, TraceEvidence) for ev in hit.trace_evidence)
    assert hit.admissible_union == cold.admissible_union
    assert hit.observed_union == cold.observed_union
    assert hit.admissible_arc_union == cold.admissible_arc_union
