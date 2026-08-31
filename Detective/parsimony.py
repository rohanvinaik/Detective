"""The SICP parsimony advisory read — Detective-native, never a proof.

Design: ``docs/PARSIMONY_ADVISORY.md``. The one invariant: **behavioural equivalence is
provable and gates rewrites; SICP parsimony is not provable and may only SIGNAL.** Nothing in
this module writes source, and nothing here decides whether a change is safe — it points at
*where* a human or large model driving Detective might look. The proof gate still decides
*whether*.

Structure follows Detective's discipline: the **pure decision** of each lens — the map from a
measured value to a ternary vote — is extracted into its own ``_*_vote`` function, so it converges
to a mutation-complete suite (scalar in, vote out). The thin lens *readers* that walk an AST node or
read a ``ScopeMap`` are the harvest/unit class (a domain object no grid synthesises); they are
covered when ``diagnose`` exercises them, not pinned cold.

Sign convention everywhere: **+1 = parsimonious/clean · 0 = no opinion · −1 = smell (look here)**.
The zero is informational (it means "this lens has nothing to say", never "disagreement"), which is
what lets non-commensurable axes vote together without a hand-tuned weighted sum — the failure mode
both recommendation-engine prototypes (Yami, ModelAtlas) were written to document.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace

from .cognitive_complexity import compute_cognitive_complexity
from .decompose_apply import _aug_targets, _names, structural_bindings
from .purity import is_pure
from .scope import ScopeMap

# ─────────────────────────────────────────────────────────────────────────────
# Structural constants (no free parameter — grounded, not fitted).
# ─────────────────────────────────────────────────────────────────────────────

# A function wider than Detective's own clean-extraction interface bound is a wide-interface
# smell. Reused from `decompose.find_extraction_candidates(max_params=4)` on purpose: it is the
# same "what is a small interface" line the prover already draws, not a number invented here.
_MAX_CLEAN_PARAMS = 4

# ─────────────────────────────────────────────────────────────────────────────
# Calibration backstops — the ONLY two numeric cutoffs in the module (every other lens is a
# structural rule with no free parameter). Calibrated on 527 module-level functions across the
# Detective + Wesker source (2026-08-06), chosen as LOOSE backstops in the distribution's tail —
# NOT fitted to examples: the −1 (smell) cutoffs sit at ≈p90, the +1 (clean) cutoffs below the
# median. Distribution — cognitive complexity: median 3 · p90 17 · max 110; DOF/line: median 1.29
# · p90 2.47 · p95 2.95 · max 6.18. Re-measure and update here if the corpus changes materially.
# ─────────────────────────────────────────────────────────────────────────────

_CC_SMELL = 15  # ≈p90 (and the Sonar default); cognitive complexity at/above this votes −1
_CC_CLEAN = 5  # below median; at/below this votes +1
_OVERLOAD_SMELL = 2.5  # ≈p90; mutation-DOF per line at/above this votes −1
_OVERLOAD_CLEAN = 1.0  # below median; at/below this votes +1

# The mined ZEROS (Wave 0 / EXP-DS-001, docs/theory/deterministic_sicp/): the five-tuple position
# is a signed deviation from the corpus norm, and these are the norms — the MEDIANS of the same
# 527-function Detective+Wesker calibration recorded above (2026-08-06), not new numbers. The
# vote cutoffs above stay the ternary thresholds; the zero is what `depth` is measured FROM.
_CC_ZERO = 3.0  # median cognitive complexity — the complexity lens's mined zero
_OVERLOAD_ZERO = 1.29  # median mutation-DOF per line — the overload lens's mined zero


@dataclass(frozen=True)
class ParsimonyLens:
    """One lens's read of one function. ``vote`` is the ternary projection; ``raw`` is the
    measured value it came from (kept for attribution and ``--full``); ``measured`` carries
    provenance — a lens whose input was not actually measured must vote 0, never −1, so
    "we did not measure this" never renders as "we measured it and it is a smell"."""

    name: str
    vote: int  # -1 smell | 0 no-opinion | +1 clean
    raw: float | int | str | bool
    detail: str
    measured: bool = True
    # The five-tuple promotion (Wave 0 / EXP-DS-001, docs/theory/deterministic_sicp/): the read
    # keeps the norm it was read against and its distance from it, so the raw fact, the signed
    # read, AND its zero sit in one row (the Peitho ledger law — never a bare score). Additive
    # and defaulted: every pre-Wave-0 constructor and consumer is untouched.
    depth: float = 0.0  # distance from the zero (`deviation_depth` — one pinned rule for all)
    zero_state: float | None = None  # the mined/structural zero; None = categorical (sign only)
    path: tuple = ()  # provenance nodes (e.g. which seam was priced) — the explainability channel


@dataclass(frozen=True)
class ParsimonySignals:
    """The fused per-function advisory read. Built in step 3 (`parsimony_from_function`);
    defined here so the scaffold's types are complete. ``flagged`` is a ≥2-lens consensus on
    −1, never a magnitude sum; ``dominant`` is the attribution channel (which lens drove it)."""

    lenses: tuple[ParsimonyLens, ...]
    flagged: bool
    agreement: int  # count of −1 lenses (the interference strength)
    dominant: str | None  # strongest −1 lens, else None


# ─────────────────────────────────────────────────────────────────────────────
# Pure decisions — the ternary votes. Scalar in, vote out → these are what Detective pins.
# ─────────────────────────────────────────────────────────────────────────────


def deviation_depth(value: float, zero: float | None) -> float:
    """The five-tuple ``depth`` — a lens value's distance from its mined zero (Wave 0 /
    EXP-DS-001, pure — pinned). One rule for every lens, so depth is never re-derived per
    reader: the fractional deviation ``|value − zero| / zero`` for a positive numeric zero
    (the Peitho geometry — unit-free, comparable across lenses); the raw distance
    ``|value − zero|`` when the zero is 0 (a count whose clean state is absence, where a
    fraction is undefined); 0.0 when the lens has no numeric zero at all (categorical —
    the position carries sign only). Split out because two of those regimes look alike at
    a call site and must not collapse into one formula."""
    if zero is None:
        return 0.0
    if zero == 0:
        return abs(value)
    return abs(value - zero) / zero


def _gamma_seam_vote(n_candidates: int, best_interface: int) -> int:
    """The γ-seam read (Wave 0 / EXP-DS-001, pure — pinned): does the CHEAPEST available
    extraction seam have a near-independent interface? SC Thm 3.15/3.16: σ(A∘B) ≤ σ(A)+σ(B)+γ,
    γ = 0 exactly for specification-independent components, γ bounded by the interface-mutant
    surface — which lives on the variables crossing the seam, so the static crossing count is
    the honest cheap proxy for the γ bound's SCALE (never γ itself; the detail must say so).

    Structural rule anchored to decompose's OWN admissibility gates, no fitted number:
    candidates arrive already bounded at ≤4 in / ≤2 out (`find_extraction_candidates`), so the
    crossing count ranges 1..6. ``≤ 2`` (one value in, one out — the cleanest non-trivial seam)
    → +1: a γ-clean split is available. ``≥ 5`` (at the gate ceiling) → −1: every seam this
    body offers leaks a wide interface, so the split-vs-bloat trade is priced AGAINST splitting
    here. ``0 candidates`` → 0: seam EXISTENCE is `_seam_vote`'s question, not this lens's —
    with no seam there is no interface to price, and the two must not collapse."""
    if n_candidates == 0:
        return 0
    if best_interface <= 2:
        return 1
    if best_interface >= 5:
        return -1
    return 0


def _regime_vote(regime: str) -> int:
    """Behavioural entanglement. Regime B (≥2 surviving mutation categories) is the behavioural
    "this is more than one thing" signal → −1; regime A is tractable → +1."""
    return -1 if regime == "B" else 1


def _seam_vote(n_seams: int) -> int:
    """A structural extraction seam left inline is a separable responsibility not yet taken →
    −1 (look here); no clean seam means the body is structurally atomic → +1. Never a proof: a
    seam is a candidate, and taking it still passes through `decompose --apply`'s proof gate."""
    return -1 if n_seams >= 1 else 1


def _width_vote(n_params: int) -> int:
    """Interface width. Wider than Detective's own clean-extraction bound is a smell → −1; a
    0–1 param interface is SICP-clean → +1; in between there is no opinion → 0."""
    if n_params > _MAX_CLEAN_PARAMS:
        return -1
    if n_params <= 1:
        return 1
    return 0


def _purity_vote(pure: bool) -> int:
    """A pure function is SICP-clean → +1. Impurity ALONE is not a smell: much state is
    essential (I/O), and we cannot mechanically tell gratuitous from essential — so impurity is
    the informational zero, contributing only by AGREEING with other lenses, never a lone −1."""
    return 1 if pure else 0


def _complexity_vote(cc: int) -> int:
    """Cognitive complexity → vote. TO CALIBRATE (step 4): `_CC_SMELL`/`_CC_CLEAN` are
    provisional loose backstops, not fitted. The comparison STRUCTURE is final; the constants
    move once measured on the real corpus."""
    if cc >= _CC_SMELL:
        return -1
    if cc <= _CC_CLEAN:
        return 1
    return 0


def _overload_vote(dof_density: float) -> int:
    """Behavioural overload — Wesker mutation-DOF (behavioural dimensions) per line, the signal
    no pure linter can see. TO CALIBRATE (step 4): `_OVERLOAD_SMELL`/`_OVERLOAD_CLEAN` are
    provisional. High density = many distinct behaviours crammed into one function → −1."""
    if dof_density >= _OVERLOAD_SMELL:
        return -1
    if dof_density <= _OVERLOAD_CLEAN:
        return 1
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Lens readers — thin shells: measure a raw value, defer to the pure vote, build the lens.
# Harvest/unit class (they take an AST node or a ScopeMap — a domain object), not pinned cold.
# ─────────────────────────────────────────────────────────────────────────────


def _param_count(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Total declared parameters across every kind — mirrors `block_interface`'s arg gather so
    the two agree on what "an interface" is."""
    a = func.args
    n = len(a.args) + len(a.posonlyargs) + len(a.kwonlyargs)
    if a.vararg is not None:
        n += 1
    if a.kwarg is not None:
        n += 1
    return n


def complexity_lens(func: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsimonyLens:
    cc = compute_cognitive_complexity(func)
    return ParsimonyLens(
        "complexity",
        _complexity_vote(cc),
        cc,
        f"CC {cc}",
        depth=deviation_depth(float(cc), _CC_ZERO),
        zero_state=_CC_ZERO,
    )


def purity_lens(func: ast.FunctionDef | ast.AsyncFunctionDef, *, is_method: bool = False) -> ParsimonyLens:
    pure = is_pure(func, is_method=is_method)
    # Categorical: no numeric zero, sign only (and the sign is never −1 — impurity abstains).
    return ParsimonyLens("purity", _purity_vote(pure), pure, "pure" if pure else "impure (state)")


def interface_width_lens(func: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsimonyLens:
    n = _param_count(func)
    return ParsimonyLens(
        "interface_width",
        _width_vote(n),
        n,
        f"{n} parameter(s)",
        depth=deviation_depth(float(n), 1.0),  # zero = the 1-param SICP-clean interface
        zero_state=1.0,
    )


def regime_lens(scope: ScopeMap) -> ParsimonyLens:
    # regime is mutation-derived: meaningful only if there was something to kill with.
    measured = scope.tests_discovered != 0 and not scope.trace_truncated
    return ParsimonyLens(
        "regime",
        _regime_vote(scope.regime),
        scope.regime,
        f"{scope.regime}",
        measured=measured,
        depth=1.0 if scope.regime == "B" else 0.0,  # categorical distance: entangled or not
    )


def seam_lens(scope: ScopeMap) -> ParsimonyLens:
    # decompose_seams is a pure structural (AST) count — always measured.
    n = scope.decompose_seams
    return ParsimonyLens(
        "seam", _seam_vote(n), n, f"{n} seam(s)", depth=deviation_depth(float(n), 0.0), zero_state=0.0
    )


def seam_lens_static(func: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsimonyLens:
    """The seam read for func-only callers (the static map, the EXP-DS-001 audit) — the same
    count `seam_lens` reads off a ScopeMap, taken from the AST directly. A failed scan abstains
    (vote 0, ``measured=False``), never votes clean: "we could not look" and "we looked and the
    body is atomic" must not render identically (the map's old manual construction conflated
    them — seams=0 on exception voted +1)."""
    try:
        from .decompose import find_extraction_candidates

        n = len(find_extraction_candidates(func))
    except Exception:  # noqa: BLE001 — an advisory read must never fail its caller
        return ParsimonyLens("seam", 0, 0, "seam scan failed", measured=False)
    return ParsimonyLens(
        "seam", _seam_vote(n), n, f"{n} seam(s)", depth=deviation_depth(float(n), 0.0), zero_state=0.0
    )


def gamma_seam_lens_from_candidates(candidates: tuple) -> ParsimonyLens:
    """Build the γ-seam read from an already-computed candidate tuple (shared by
    :func:`gamma_seam_lens` and the static map, so a repo scan enumerates seams once).
    ``raw``/``depth`` = the crossing count of the CHEAPEST seam — the static proxy for the
    γ bound's scale (SC Thm 3.16: γ ≤ the interface-mutant surface, which lives on the
    crossing variables). The detail says "proxy" because γ is bounded here, never measured;
    ``path`` carries which seam was priced (provenance — the Peitho five-tuple law)."""
    n = len(candidates)
    if n == 0:
        return ParsimonyLens("gamma_seam", _gamma_seam_vote(0, 0), 0, "no seam to price", zero_state=0.0)
    best = min(candidates, key=lambda c: len(c.inputs) + len(c.outputs))
    width = len(best.inputs) + len(best.outputs)
    return ParsimonyLens(
        "gamma_seam",
        _gamma_seam_vote(n, width),
        width,
        f"{width} crossing(s) at the cheapest seam (γ-bound proxy)",
        depth=deviation_depth(float(width), 0.0),
        zero_state=0.0,  # γ = 0 — the specification-independent seam — is the zero
        path=(f"lines {best.start_line}-{best.end_line}",),
    )


def gamma_seam_lens(func: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsimonyLens:
    """The γ-seam bank (Wave 0 / EXP-DS-001): price the cheapest available extraction seam by
    its interface, off the AST alone. Abstains (``measured=False``) when the scan itself fails —
    the same honesty rule as :func:`seam_lens_static`."""
    try:
        from .decompose import find_extraction_candidates

        candidates = find_extraction_candidates(func)
    except Exception:  # noqa: BLE001 — an advisory read must never fail its caller
        return ParsimonyLens("gamma_seam", 0, 0, "seam scan failed", measured=False)
    return gamma_seam_lens_from_candidates(candidates)


def overload_lens(scope: ScopeMap, line_span: int) -> ParsimonyLens:
    """Behavioural overload = mutation-DOF (the mutant universe = behavioural-dimension count)
    per line of the function. `line_span` is the function's executable extent, supplied by the
    caller (the reader that holds the AST); density normalises out mere length."""
    dof = scope.specification.behavioral_variants
    density = dof / max(1, line_span)
    measured = scope.tests_discovered != 0 and not scope.trace_truncated
    return ParsimonyLens(
        "overload",
        _overload_vote(density),
        round(density, 2),
        f"{dof} DOF / {line_span} ln",
        measured=measured,
        depth=deviation_depth(density, _OVERLOAD_ZERO),
        zero_state=_OVERLOAD_ZERO,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cohesion — the one metric with no upstream computer. A statement-level LCOM-analogue: does
# the function compute ONE thing, or several unrelated things sharing only a scope? Built on the
# SAME read/write-set primitives `block_interface` uses, so the two agree on what "data" is.
# ─────────────────────────────────────────────────────────────────────────────


def _cohesion_vote(n_components: int) -> int:
    """Statement-level def-use components → vote. Structural, no free parameter: exactly one
    component is one computation → +1; two or more independent responsibilities share only a
    scope → −1; fewer than two data-touching statements is trivial → 0 (no opinion)."""
    if n_components == 0:
        return 0
    if n_components == 1:
        return 1
    return -1


def statement_cohesion(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Number of weakly-connected components in the function's statement-level def-use graph.

    A statement's data footprint is the names it reads/writes (via ``_names``/``_aug_targets``)
    MINUS the names it binds for itself (``structural_bindings`` — the loop-variable leak a naive
    reads∩writes test gets wrong). Two statements are connected when their footprints share a name
    that is *produced somewhere in the function* (``internal_writes``) — an INTERNAL def-use tie,
    not two statements merely both reading the same external parameter (which is not evidence of
    one responsibility). Components are counted only over data-touching statements; a leading
    docstring or a bare ``return`` has an empty footprint and is ignored.

    Nodes are PRODUCER statements (they write an internal name). A pure *sink* — a ``return``,
    a bare side-effect call — consumes chains but must NOT merge them: packaging two independent
    results into one ``return y, q`` is output collection, not a data tie between the two
    productions. (Counting sinks as nodes collapses every function to one component — caught in
    validation: two disjoint chains read as 1 until sinks were excluded.)

    1 component = one computation (cohesive). ≥2 = independent responsibilities sharing a scope
    (an incohesion smell). 0 = fewer than two producer statements (trivial — no opinion). Data
    cohesion only: a function of pure side-effect calls, or one whose state is attribute writes
    (``self.x =``, not a local Name), has no producer graph and abstains here — honestly 0.
    """
    footprints: list[set[str]] = []
    reads_per: list[set[str]] = []
    writes_per: list[set[str]] = []
    internal_writes: set[str] = set()
    for stmt in func.body:
        binds = structural_bindings(stmt)
        reads = (_names(stmt, ast.Load) | _aug_targets(stmt)) - binds
        writes = (_names(stmt, ast.Store) | _aug_targets(stmt)) - binds
        reads_per.append(reads)
        writes_per.append(writes)
        footprints.append(reads | writes)
        internal_writes |= writes

    keys = [fp & internal_writes for fp in footprints]
    idx = [i for i in range(len(func.body)) if writes_per[i]]
    if len(idx) < 2:
        return 0

    parent = {i: i for i in idx}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Producer↔producer edges: two producers tie when their footprints share an internal name
    # (one writes what the other reads, or they co-write a name).
    for a_pos in range(len(idx)):
        for b_pos in range(a_pos + 1, len(idx)):
            i, j = idx[a_pos], idx[b_pos]
            if keys[i] & keys[j]:
                union(i, j)

    # Combining sinks: a statement that writes no internal name but CONSUMES several producers —
    # a single ``return expr``, a ``return f(x, p)``, a bare side-effect call — fuses them into one
    # computation (many→one is a real combination). The one exception is a top-level tuple
    # ``return x, p``: the Python idiom for returning SEVERAL values, i.e. bundling independent
    # results, which must NOT merge them. (This decision is what separates a cohesive struct-builder
    # from a function that returns two unrelated values — both look identical without it.)
    producers_of: dict[str, list[int]] = {}
    for i in idx:
        for name in writes_per[i]:
            producers_of.setdefault(name, []).append(i)
    for i, stmt in enumerate(func.body):
        if writes_per[i]:
            continue
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Tuple):
            continue
        consumed = [p for name in (reads_per[i] & internal_writes) for p in producers_of.get(name, [])]
        for other in consumed[1:]:
            union(consumed[0], other)

    return len({find(i) for i in idx})


def cohesion_lens(func: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsimonyLens:
    n = statement_cohesion(func)
    if n == 0:
        detail = "trivial (< 2 data statements)"
    elif n == 1:
        detail = "1 data-flow component"
    else:
        detail = f"{n} disjoint components"
    # zero = 1 component (one computation); n == 0 is trivial — no measured position, depth 0.
    return ParsimonyLens(
        "cohesion",
        _cohesion_vote(n),
        n,
        detail,
        depth=deviation_depth(float(n), 1.0) if n else 0.0,
        zero_state=1.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fusion — consensus over ternary votes, never a weighted sum. The pure combiners are what
# Detective pins (tuple-of-votes in, verdict out); `parsimony_from_function` is the thin
# assembly (it holds an AST node + a ScopeMap — the harvest/unit class).
# ─────────────────────────────────────────────────────────────────────────────

# Attribution priority: the behavioural + structural lenses carry the most design weight, so
# when several agree they name the flag. Order here IS the order the lenses are built below.
# Wave 0 additions: gamma_seam (right after seam — its sibling: seam says A SEAM EXISTS, gamma
# prices it) and purity (last — it never votes −1, so its position never names a flag; it is in
# the signature for the discrimination guarantee, not the smell consensus).
_LENS_PRIORITY = (
    "overload",
    "cohesion",
    "regime",
    "seam",
    "gamma_seam",
    "complexity",
    "interface_width",
    "purity",
)


def _agreement(votes: tuple[int, ...]) -> int:
    """How many lenses vote −1 (smell). The interference strength — cross-lens consensus, the
    honest fusion of non-commensurable axes. Thresholding to {−1,0,+1} upstream is what lets
    axes on wildly different scales vote together without a hand-tuned weighted sum (the failure
    both recommendation-engine prototypes were written to document)."""
    return sum(1 for v in votes if v == -1)


def _flagged(agreement: int) -> bool:
    """Report a smell only on ≥2-lens agreement: one lens is necessary, never sufficient — the
    rule LintGate's decomposition evidence arrived at the same way, and the guard that keeps an
    advisory read from crying wolf on any single noisy axis."""
    return agreement >= 2


def _first_smell(votes: tuple[int, ...]) -> int:
    """Index of the first −1 vote (lenses are supplied in priority order), else −1. Names the
    dominant lens deterministically, without ever comparing the incommensurable raw values."""
    for i, v in enumerate(votes):
        if v == -1:
            return i
    return -1


def parsimony_from_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef, scope: ScopeMap, line_span: int
) -> ParsimonySignals:
    """The per-function advisory read. Builds every lens (in `_LENS_PRIORITY` order), silences any
    whose input was not measured (vote → 0, never −1 — provenance), then fuses by AGREEMENT: a
    ≥2-lens consensus flags, and the highest-priority −1 lens is the attribution. Nothing here
    decides whether a change is safe; it points where a human/model driving Detective might look."""
    built = (
        overload_lens(scope, line_span),
        cohesion_lens(func),
        regime_lens(scope),
        seam_lens(scope),
        gamma_seam_lens(func),
        complexity_lens(func),
        interface_width_lens(func),
        # Methodness is not knowable from the node alone (an ast name is never dotted), so this
        # reads every target as a plain function: a method's self-attribute writes then read as
        # impure → purity votes 0 — honest abstention, never a false smell (its only other vote
        # is +1, so the safe direction is built into the lens).
        purity_lens(func),
    )
    lenses = tuple(lens if lens.measured else replace(lens, vote=0) for lens in built)
    votes = tuple(lens.vote for lens in lenses)
    agreement = _agreement(votes)
    dominant_idx = _first_smell(votes)
    dominant = lenses[dominant_idx].name if dominant_idx >= 0 else None
    return ParsimonySignals(
        lenses=lenses, flagged=_flagged(agreement), agreement=agreement, dominant=dominant
    )
