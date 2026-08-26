"""#67: the coupling-aware band kills a survivor gated behind a value-referential conditioning edge.

A worklist over records whose keys come from a SECOND parameter is only reachable by inputs that tie
the two parameters together — the referencing parameter must name into the records' key field. The
scalar grid samples parameters independently and never builds that tie, so the coupled mutant
survives as an *unreached* candidate-equivalent — the exact false-`equivalent`-flag hazard #67 names.
`conditioning_edge` extracts the edge as a dataflow fact and `_referential_inputs` builds the tie
(cross-referential records + seeds that name into them), so the survivor becomes a proven KILL.

Contract pinned here is the classify-level one the sibling bands (B0/B1/B2/B3) are held to: WITH the
band, `report.killable` grows over WITHOUT it. Positive-only, so turning the band off can only lose
kills, never change a sound verdict.
"""

from __future__ import annotations

import ast
import textwrap

import Detective.engine as engine
from Detective.engine import classify_survivors
from Detective.equivalence import conditioning_edge

_TC = """
def transitive_close(items, seeds):
    by_name = {it[0]: it for it in items}
    reached = set()
    frontier = list(seeds)
    out = []
    while frontier:
        n = frontier.pop()
        if n in reached or n not in by_name:
            continue
        reached.add(n)
        it = by_name[n]
        out.append(it[1])
        for d in it[2]:
            if d not in reached:
                frontier.append(d)
    return sorted(reached), "".join(out)
"""


def _write(tmp_path) -> str:
    (tmp_path / "tc.py").write_text(textwrap.dedent(_TC).lstrip())
    # A deliberately weak covering test: name == source, no multi-hop deps — so an index-swap and the
    # closure-loop mutations are reached-but-undistinguished, i.e. exactly the coupled residual.
    (tmp_path / "test_tc.py").write_text(
        "from tc import transitive_close\n\n\n"
        "def test_happy():\n"
        "    assert transitive_close([['a', 'a', []]], ['a']) == (['a'], 'a')\n"
    )
    return str(tmp_path)


def test_conditioning_edge_is_extracted_on_the_target():
    node = ast.parse(textwrap.dedent(_TC).lstrip()).body[0]
    assert conditioning_edge(node) == (0, 0, 1)  # items keyed on field 0, seeds the referencer


def test_coupling_band_kills_a_referential_survivor_the_grid_leaves(tmp_path, monkeypatch):
    root = _write(tmp_path)
    # OFF: the coupling generator returns nothing, so the survivors behind the edge stay candidate-equivalent.
    monkeypatch.setattr(engine, "_referential_inputs", lambda *a, **k: [])
    without = classify_survivors("tc.py", "transitive_close", root, deadline_s=None)
    kills_without = len(without.killable)
    monkeypatch.undo()
    # ON: the coupling tie is built, and the previously-unreached survivors are proven killable.
    with_band = classify_survivors("tc.py", "transitive_close", root, deadline_s=None)
    assert len(with_band.killable) > kills_without, (kills_without, len(with_band.killable))
