"""Suggested-witness deduplication (issue #18).

Field shape: one (input, expected) pair killed twelve distinct mutants and
the report printed the identical 800-char assert twelve times. The grouped
form states the useful fact — one pin closes N degrees of freedom — and names
the mutant ids so the mapping stays auditable.
"""

from __future__ import annotations

from Detective.cli import _format_survivor_report
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness


def _killable(mutant_id: str, args: tuple, original: object) -> MutantVerdict:
    return MutantVerdict(
        mutant_id=mutant_id,
        category=mutant_id.split("_")[0],
        diff_summary="- x + y",
        killable=True,
        witness=Witness(args=args, original=original, mutant="<other>"),
        searched=5,
    )


def test_identical_witnesses_collapse_to_one_line_with_kill_set():
    rep = SurvivorReport(
        verdicts=(
            _killable("VALUE_aaaa1111", (3, 4), 7),
            _killable("SWAP_bbbb2222", (3, 4), 7),
            _killable("BOUNDARY_cccc3333", (9,), 81),
        ),
        unclassified=(),
    )
    out = "\n".join(_format_survivor_report(rep, verbose=False))
    arrows = [ln for ln in out.splitlines() if "→ assert" in ln]
    assert len(arrows) == 2, out
    shared = next(ln for ln in arrows if "(kills 2:" in ln)
    assert "VALUE_aaaa1111" in shared
    assert "SWAP_bbbb2222" in shared
    solo = next(ln for ln in arrows if "81" in ln)
    assert "kills" not in solo
    # The header still counts VERDICTS, not lines — three killable mutants.
    assert "not auto-applied, 3" in out
