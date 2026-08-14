# The Function Basis — an overhaul of test discovery, scoping, and proof accounting

**Status:** design, pre-build. Nothing here is implemented.
**Home:** Detective (the law, the universe, the basis) + Wesker (the router, the tracer).
**Question:** *given `file.py::function`, which tests are admissible evidence about it, and when
have we got enough?*

---

## Constraints

Three, from which most of the design follows.

> **1 · No new command.** `diagnose · converge · decompose · audit · purge · regime · flag ·
> flag-line · parsimony · receipt · verify-rewrite` is complete and already partitions this
> question correctly. A spec arguing that one question is answered in too many places may not
> answer it in one more.
>
> **2 · No new module.** This is a **rewiring**, never an addition. Net **−1 module if C1's ARC
> measurement lands** (§13): `reachability.py` is deleted and its surviving facts move into
> `regime.py`. If ARC shows the import closure is load-bearing in the sparse regime, that closure
> survives as an **ordering-only Layer-2 prior** and the module count is unchanged. The deletion
> headline is a bet on an unrun external measurement (#9, yours); everything in Phases A, B, D, E
> and F is sound either way.
>
> **3 · The decisions almost all exist and are already pinned.** Nine pure functions (§5.1)
> survive verbatim; exactly **one is added** — `basis_membership` (§9), authored and pinned in D1.
> What is otherwise rebuilt is the plumbing between them.

### Provenance convention

Every factual claim is tagged so it can be audited independently of this document.

| tag | meaning |
|---|---|
| **[M]** | measured in this repo; command and numbers given |
| **[V]** | verified by reading current source; `file:line` given |
| **[C]** | quoted from a commit message; sha given |
| **[R-wire]** | survey-agent **wiring** claim (who calls this / is it referenced) — re-confirm with `find_referencing_symbols` |
| **[R-exec]** | survey-agent **behavioural** claim (what does it compute) — re-confirm by **re-running the direct-execution probe**. References cannot settle these: a single-seam reference structure is entirely consistent with a non-identity function |
| **[P]** | this document's proposal, not a fact |
| **[?]** | open decision — needs a ruling before the slice that depends on it |

---

# The scoping correction — sound reachability is an ELIGIBILITY BOUND, not a forbidden exclusion

**Recorded 2026-08-14, after the ARC C1 measurement falsified the C-phase premise. This section
OVERRIDES the conclusions of §3 (the "only Layer 3 excludes" reading), §4.1, §4.3, §7 and §13 that
argued Layer 1's reachability filter should be DELETED. Those sections are kept for their
measurements; their *conclusion* is struck. Read this first — it is the central purpose of the
system, not a footnote.**

**Core purpose: scoped suite + synthesis, NEVER a whole-suite grind.** The sandwich thesis says the
unit is ONE function's operators and ONE function's tests. Operationally: discover the tests that
could kill this function's mutants (the *reachable* set), run those, and when they do not kill every
mutant, **drop to synthesis** (generate a killing test) — never trace the rest of the suite hoping a
distant test covers. "Discoverable tests + mutant-killing synthesis" is the design, and it is
achievable.

**Why scoping is sound — the distinction the delete-Layer-1 argument missed.** Two different
questions were collapsed into one:

- **Certificate exclusion** — marking a test `disjoint` (does-not-cover) WITHOUT observing it. The
  Law rightly forbids this (§2.1: absence ≠ falsehood; a never-traced test is `unknown`, never
  `disjoint`). Only Layer 3 (observation) may write an exclusion into the proof basis.
- **Eligibility bound** — deciding which tests are even worth TRACING for this target. This is NOT a
  certificate claim, and static reachability MAY bound it soundly.

A mutant changes one of the target's lines; a test kills it only by EXECUTING that line, which
requires (transitively) calling the target. Therefore **a test that provably cannot reach the target
provably cannot kill any of its mutants** — not tracing it discharges nothing and hides nothing. So a
`gap` (§1.3, "every eligible unknown resolved") requires exhausting only the **reachable** unknowns,
not the whole collection. Eligibility = `reachable(target)`; bounding the search by it is a
soundness-preserving optimization, not a Layer-1 exclusion. This is what makes §1.2's "no reason to
trace the whole suite" *operational* rather than aspirational.

**The one condition: reachability must be a correct OVER-approximation** — it may over-*include*
(trace a few irrelevant tests) but must NEVER call a real reacher unreachable. The old
`reachability.py` was built exactly this way ("ANY doubt returns None / includes the file"). §4.3's
conftest-fixture hole was an UNDER-approximation BUG (a missed fixture edge → a wrongly-excluded
reacher → a lost kill) — a fixable defect, not proof the approach is impossible.

**Why the delete-Layer-1 argument was over-motivated:**
- §4.1 "does not discriminate on a cohesive package" (Detective 129/180) is a DENSE-repo observation —
  there the covering set genuinely IS most of the suite. Scoping is for SPARSE repos (ARC 96→13),
  where it is essential. "Doesn't help dense" is not "delete it."
- §4.3 "unsound" is a specific missed-edge bug, closed by COMPLETING the over-approximation (conftest
  fixtures, dynamic dispatch → opaque), not by deleting the analysis.

**Measured (ARC `serialize_rule`, C1):** deleting Layer 1 held verdict-parity (18/24) but blew the
widen's eligible-unknown pool **12 → 423**, grinding ~330 traces through slow irrelevant tests. F1
(ordering-only, §11) *cannot* recover it: ordering cannot reduce a sound exhaustion, and
`serialize_rule`'s 6 residual obligations are undischargeable by ANY suite test, so no re-rank
discharges them. The recovery is not F1 — it is the sound eligibility bound above, plus
drop-to-synthesis for the residual.

**Consequence for the plan.** C1 (delete Layer 1) is **REVERTED**. `collection_universe` (the
target-agnostic Layer-1 universe) STAYS. The C-phase becomes: **restore a SOUND over-approximating
reachability scope as the eligibility bound** (fix its conftest-fixture / dynamic holes — the real
§4.3 defect), **and route the un-killed residual to synthesis**. The Three-Layer Law (§3) is amended:
"only Layer 3 may EXCLUDE (from the certificate)" stands; eligibility for the widen may be soundly
bounded by an over-approximating reachability at Layer 2, because a provably-unreachable test is not
a certificate claim — it is work that provably cannot contribute.

---

# Part I — The object

## 1. What is actually being computed **[P]**

### 1.1 Not the covering population

The tempting object is *every test that executes the function*:

$$\mathrm{Cov}^{-1}(t) = \{\, \tau \in \mathcal{T} : \tau \text{ executes a line of } t \,\}$$

**This is the wrong target.** In dynamic Python it is only computable by executing every collected
test under the live runtime context — fixtures, hooks, dynamic imports, dispatch, monkeypatching,
parametrization, plugins. Any static approximation must choose between missing covering tests and
admitting irrelevant ones. Aiming at it is what produced a repo-walking import graph that
discriminates nothing (§4.1) and a whole-suite baseline trace.

### 1.2 The right object: a sufficient, admissible basis

The Sandwich does not need the covering population. It needs enough evidence to discharge one
function's obligations.

$$O_t \;=\; L_t \;\cup\; A_t \;\cup\; M_t$$

- $L_t$ — executable-line obligations (`executable_lines`, the static denominator)
- $A_t$ — arc obligations (branch transitions with both endpoints in $L_t$)
- $M_t$ — semantic mutation dimensions (the generated mutant set)

Each admissible executed test discharges some subset $E(\tau, t) \subseteq O_t$. A set $B_t$ is a
**proof basis** for $t$ when

$$\bigcup_{\tau \in B_t} E(\tau, t) \;=\; O_t \setminus U_t$$

where $U_t$ is the **undischargeable residue** — candidate-equivalent mutants and lines flagged
unreachable. $U_t$ is reported, never absorbed.

**The consequence that makes everything else small:** tests outside $B_t$ need not be shown
disjoint. They are simply *unnecessary to this certificate*. There is no obligation to classify
the whole suite, and therefore no reason to trace it.

This is already what the engine does — `next_routing_action` stops "the instant obligations
discharge" **[C]** (`3280ebe`) over normalized obligations (survivors + provisional-equivalents +
uncovered lines). The model here names the object that mechanism was always computing.

### 1.3 The four terminal states

`next_routing_action`'s existing states, read against the model:

| state | meaning | gateable? |
|---|---|---|
| `complete` | $\bigcup E = O_t \setminus U_t$ | yes |
| `trace_next` | obligations open, eligible unknowns remain | — keep widening |
| `gap` | obligations open, **every** eligible unknown resolved | yes — a real specification gap |
| `unresolved` | obligations open, unknowns remain, budget cut | **no** — never reported as a gap **[C]** (`303289b`) |

The `gap`/`unresolved` distinction is the whole risk model in one row: a negative conclusion is
valid only when the search was exhausted, never when it was truncated.

### 1.4 The basis is path-dependent, and the certificate must say so **[P]**

$B_t$ is found greedily in stratum order, so it is a *minimal sufficient* set, not a canonical
one. Different `.wesker/` trace-cache state yields a different $B_t$ **[R-exec]** — *"the same verdict,
a different `line_coverage` domain."* The same shape as the recorded live-session scored-count
noise.

The verdict is stable; the basis is not. Two obligations follow:

- **`audit`'s minimality numbers are basis-relative, not suite-relative.** Minimal cover, bloat,
  and redundancy must be labelled as computed over $B_t$, not over the suite.
- **`audit --remove` may only propose removing a test it actually traced.** A test outside $B_t$
  was never measured; proposing its deletion is a claim the run did not earn. This sharpens #54
  and meets the theory doc's κ-gated removal from a new direction.

---

## 2. The evidence algebra **[P]**

Two independent axes decide what an observation may do. Conflating them is the recurring defect
(§4.6).

### 2.1 Freshness × sign

| observation | may enter $B_t$ (proof) | may order | may exclude |
|---|---|---|---|
| **positive, fresh, admissible** | ✅ | ✅ | — |
| **positive, fresh, inadmissible** (inert / baseline-failing / truncated / uncontained) | ❌ | ✅ | — |
| **positive, replayed from cache** | ❌ | ✅ | — |
| **negative, fresh, outcome-qualified, in-session** | — | ✅ | ✅ |
| **negative, replayed** | — | ✅ | ✅ only under a complete regime (§2.2, B3) |
| **absent** (never observed) | ❌ | — | ❌ |

Two rules carry it, and both already exist in the codebase as invariants:

> **Gateability is absorbing.** No path turns an inadmissible observation into an admissible one.
>
> **Absence is not falsehood.** A test never traced is `unknown`, never `disjoint`.

### 2.2 [RESOLVED — B3] May a replayed negative exclude? — yes, under a complete regime

A replayed negative is what lets routing skip a known-disjoint test without re-tracing it. It is
also the only cached value that can *shrink* the search, i.e. the only one that could manufacture
a false `COMPLETE`.

**Grounding [V].** The current implementation does **not** promote cached absence to non-reach —
`trace_cache.py:315-316` returns `continue` on a cache miss, leaving the item `unknown`.
`not_reached` (`:323`) requires *all* of: a hit under a content fingerprint that includes the
bytes of every ancestor `conftest.py` and every fixture-origin file (`test_fingerprint:125-151`);
a `load()` keyed on regime digest, targets fingerprint and budgets; **and** a completed
baseline-outcome pass at the same fingerprint. The `os.urandom` nonce at `:146-149` exists so two
unreadable contexts cannot compare equal and *"promote stale non-reach to impossible."*

So the rule is **conditionally sound**, and the condition is exactly Wesker #20 — whether the
context digest is *complete*. **Grounded (B3):** #20's "unkeyed" list was mostly stale.
`regime_digest` (`session_manifest.py`) already keys rootdir, inipath, import mode, and the sorted
plugin set (dist plugins by version, local plugins/conftests by path+content), and refuses to `""` —
uncacheable — on any unobserved/unreadable plugin; `pytest_generate_tests` rides its conftest's
content. Only **two** residuals were real: the config-file **content** (only its path was keyed) and
the **Hypothesis seed** (a property test's covered lines vary per example).

**Ruling: option (a) — make the precondition checkable — implemented in B3 (Wesker `05be94d`).**
Both residuals are closed: (a-1) `capture_manifest` binds `inicontent_digest = _digest(inipath)` at
build, folded into `regime_digest` (pure — a hash of the frozen snapshot, never a property that
reads the FS); and (a-2) the pinned `replayed_negative_admission(has_outcome, fingerprint_matches,
is_property_test)` degrades a Hypothesis test's cached negative to `unknown` (`✓ COMPLETE · 9/9`),
with `_is_property_test` walking the `__wrapped__` chain. The replayed-positive rule (§2.1) is
untouched — a cached positive still only orders.

### 2.3 The two halves of the Sandwich are typed apart **[P]**

$$\mathcal{T} \;=\; \mathcal{H} \;\uplus\; \mathcal{G}$$

- $\mathcal{H}$ — hand-written tests: **intent evidence**
- $\mathcal{G}$ — generated tests: **characterization evidence**

Generated tests close mutation dimensions but cannot establish intent — they faithfully pin
behaviour that may already be wrong. This is the project's own stated doctrine (*"generated tests
are a characterization, not a review… anything wrong today is now pinned wrong"*), and it is
currently true in prose and invisible in the result object.

Attribute each discharged obligation to the half that discharged it, so a certificate can report:

```
30/30 dimensions pinned  ·  6 intent-grounded · 22 characterized · 2 unattributed
```

**Origin is a recorded fact, never a path glob.** `tests/detective/` and
`@pytest.mark.detective` are an **authorship proxy, not an intent proxy**, and they break in both
directions: a hand-written test dropped into `tests/detective/`, or a generated golden a human
later edits to encode intent. Re-deriving origin from a glob at report time is the
measurement/decision gap one level up — a filesystem proxy standing in for an evidentiary role, in
the one place the doctrine matters most.

So `Witness.origin` is set from a **recorded authorship fact**, written where authorship is
actually known: `certify._write`, the single choke point every generated test passes through on
its way to disk. Three states, and the third is not folded into either:

| origin | meaning |
|---|---|
| `characterization` | this `TestId` is in Detective's write ledger, unedited since | 
| `intent` | never written by Detective, **or** written and since edited by a human (the pins store already detects this by AST digest) |
| `unattributed` | no recorded fact — reported separately, never counted as either |

`unattributed` is the same discipline as an unmeasured parsimony lens voting 0: *"we did not
measure this"* and *"we measured it and it is clean"* must never render identically. It belongs on
`audit` and `diagnose` — the pre-`converge` question — not on `converge`, which by construction
produces only $\mathcal{G}$.

---

## 3. The Three-Layer Law **[P]**

> **Layer 1 knows no target. Layer 2 may only order. Only Layer 3 may exclude.**

| | when | granularity | knows the target? | may exclude? |
|---|---|---|---|---|
| **1 · Universe** | before collection | file (forced) | **no — forbidden by API shape** | no |
| **2 · Priority** | after collection | `TestId` | yes | **no** |
| **3 · Observation** | during execution | `TestId` | yes | **yes** (§2.1) |

Layer 1 is **universe construction**, not relevance scoping. It answers only *"what would this
pytest regime collect?"* Its signature takes a `TestRegime` and nothing else, so a target-specific
fact cannot enter it without changing the type.

**The file/item granularity split is physical.** Layer 1 must precede collection and pytest
collects files. It cannot be item-granular however it is written. This is why `file_peer` is
**correct and must be kept** in Layer 2: it is the necessary residue of a forced granularity.

---

# Part II — The current state

## 4. What is wrong

### 4.1 The static layer does not discriminate **[M]**

`reachable_test_paths` against Detective's own repo:

| target | kept | vs `adequacy.py` |
|---|---|---|
| `adequacy.py` | 129 / 180 | — |
| `cli.py` | 129 | **byte-identical** |
| `parsimony_map.py` | 129 | **byte-identical** |
| `binding.py` | 129 | **byte-identical** |
| `line_flags.py` | 131 | differs by 2 |
| `atomic_store.py` | 138 | differs by 9 |

Structural, not a bug **[V]**: `Detective/__init__.py` re-exports `certify`/`converge`/`engine`/
`scope`, so any `import Detective` reaches the package; and `engine`, `certify`, `binding`,
`typed_synthesis` are `opaque`, which by design reaches everything (`reachability.py:209-210`).

Import reachability is near-vacuous on any cohesive package. It bites only in the sparse regime
(Regenesis: 2134 → 206), and every ordinary library is dense.

### 4.2 It costs more than it saves **[M]**

```
_build_graph                 0.27 s   (226 modules — rebuilt every call, never memoized)
pytest collect, 129 paths    0.76 s
pytest collect, `tests/`     0.45 s   ← the UNSCOPED collection is FASTER
```

Wesker measured the same and **deliberately declined** **[C]** (`226b4a6`, *"NOT LANDED, and this
is the substance of #15"*): explicit paths yield origins spelled as given where the ordinary route
canonicalises, and the ordinary route *"DROPS the test whose module-level `from <target> import
...` cannot resolve."* Detective does externally what Wesker refused to do internally.

### 4.3 It has a live soundness hole **[R-exec — reproduce the synthetic repo before acting]**

A test whose only path to the target is a **conftest fixture** is silently excluded. The import
graph has no `conftest → test` edge, because pytest *injects* fixtures. Reported reproduction:
`tests/conftest.py` does `from pkg.mod import quote` and exposes it as a fixture;
`tests/test_via_fixture.py` takes only the fixture and is dropped.

The same failure Wesker already fixed **[C]** (`e860780`), reintroduced one layer up where that
fix cannot see it — and in the direction `reachability.py:13-17` says it never goes.

### 4.4 Every walk-pruning patch solves pytest's problem for it **[M]**

`_SKIP_DIRS`, `_pytest_norecursedirs`, `is_virtualenv_root` exist because Detective runs its own
`os.walk`. pytest 9.1.1's default `norecursedirs`:

```python
['*.egg', '.*', '_darcs', 'build', 'CVS', 'dist', 'node_modules', 'venv', '{arch}']
```

`.venv`, `.venv312`, `.tox`, `.git`, and every cache dir match `.*`. Only `mutants/` is missed —
a `norecursedirs` line the repo should declare, i.e. a **regime** fact.

### 4.5 Three notions of "relevant test" coexist **[V]**

| | unit | mechanism | status |
|---|---|---|---|
| **L1** `reachability.py:261` | file path | import-graph closure | decides pytest's collection |
| **L2** `Wesker/ci.py:347` | file | convention ∪ static impact map | **computed every live call, discarded** |
| **L3** `Wesker/ci.py:630` | `TestId` | evidence lattice | does all the real work |

Nothing reconciles them. `_route_live_callables` (`ci.py:506`) — the function every `#15` comment
calls "the routing seam" — was **executed directly against the local Wesker** and is the
**identity function under every production call** **[R-exec]**. A full AST parse of every candidate
test file plus a second impact map over fixture files, computed and dropped, per
`discover_test_callables`.

### 4.6 Contract violations confirmed by reading **[V]**

- `_barred` (`Wesker/engine.py:5799-5803`) has **no containment term**, while
  `admissible_line_coverage` is declared at `engine.py:433-434` to exclude *"baseline-failing,
  truncated, or uncontained."*
- `_barred` speaks **two vocabularies**: `inert_ids` (any non-pass) in a live session, `failing`
  (AssertionError only) outside one. Same field, two meanings, chosen by code path.
- `trace_cache.load_outcomes:328-347` performs **no validation** — versus `load:197-227`'s
  five-way check. The invariant holds by caller discipline, not construction.
- `verdict_cache.py:232-236` rehydrates `trace_evidence` **including `provenance='fresh'`**, so a
  warm verdict ships rows claiming they were traced this session — the live violation of §2.1's
  replayed-positive rule.
- `trace_tier` (`Detective/engine.py:795`) — backing `audit --plan` — calls
  `discover_test_callables` **without `testpaths` or `extra_dirs`**, predicting a `profile`
  (`engine.py:555`) that runs over a different universe. One of five call sites not threading the
  regime.
- Two module identities disagree: `reachability.module_name:77` names graph nodes,
  `oracle_light.importable_module:159` names the target, and `reachability.py:284` tests
  membership across the two schemes.

### 4.7 The dead ledger **[R-wire — `find_referencing_symbols` each before deletion]**

`ci.discover_tests` (the advertised 3-tier orchestrator — one referencing symbol, its own test) ·
`ci.split_live_callables` · `ci.route_admits(conservative=True)` · `ci.live_suite_active` (zero
references) · `run_function_converged`'s `widen_tests` and its ~125-line widen (a hand-mirrored
copy with a **different obligation set** — no line axis) · `unknown_dynamic` (`dynamic_uncertain`
is a literal `False` at both call sites, so the documented 7-stratum lattice is really **6**) ·
`line_coverage.trace_evidence_admissible` (a second admissibility implementation with no replay
concept — dead **and** a drift hazard) · `_is_test_filename(patterns=…)` (never passed, so a
custom `python_files` is invisible to the static selector).

### 4.8 The diagnosis is already written down **[V]**

`Wesker/session_manifest.py:3-9`:

> *"Detective reconstructs the pytest regime in at least five places… Each was improved separately
> and each is still a MIRROR: a prediction of what pytest would do, made from the same inputs but
> not by the same code."*

`PytestSessionManifest` is the only thing in the stack that **observes what pytest did** rather
than predicting what it would do. Every mirror this overhaul deletes is one prediction replaced by
that observation — the Sandwich one level down: you do not model the suite; you are *given* it.

---

## 5. What is already right

### 5.1 The decisions survive verbatim **[V]**

| decision | where | pin |
|---|---|---|
| `within_declared_testpaths` | `reachability.py:228` → moves to `regime.py` | 16/16 |
| `route_test_item` | `Wesker/ci.py` | 32/32 |
| `_unknown_stratum_rank` | `Wesker/ci.py` | 17/17 |
| `next_routing_action` | `Wesker/engine.py` | 9/9 |
| `route_admits` | `Wesker/ci.py:458` | 9/9 |
| `_activate_target_first` | `Detective/engine.py:464` | 27/27 |
| `trace_admissibility` | `Wesker/trace_evidence.py:26` | the live owner |
| `resolve_regime` / `TestRegime` | `Detective/regime.py:449` | single fact supplier |
| `seed(A) ; expand(B) ≡ get(A ∪ B)` | `Wesker/engine.py:2668` | pinned algebraic law |

### 5.2 Single-consumer seams **[V]**

| seam | production consumers |
|---|---|
| `reachable_test_paths` | 1 — `cli.py:135` |
| `partition_live_callables` | 1 — `Detective/engine.py:676` (cross-repo) |
| `observed_function_reach` | 1 — `Detective/engine.py:663` |
| `run_with_live_suite(paths=…)` | 1 — `cli.py:3992`; `paths` is the **only** collection-level knob |
| `_build_test_scope` | the single mutant→covering-tests resolver |
| `refresh_live_suite` | the single suite-invalidation path |
| `resolve_regime` | the single pytest-config fact supplier |

Every slice in Part IV touches exactly one.

---

# Part III — The target architecture

## 6. Identity **[P]**

Type aliases are not types — `TestId = str` and `FileId = str` remain interchangeable strings.
Use `NewType` and frozen records, in `regime.py`, which already owns every fact of this kind.

```python
# Detective/regime.py — the only definitions in either repo
from typing import NewType

TestId   = NewType("TestId", str)    # pytest nodeid, post-parametrization. NEVER __name__.
ModuleId = NewType("ModuleId", str)  # target-module name. ONE producer AFTER C1 folds
                                     # oracle_light.importable_module → regime.module (today two, §4.6).


@dataclass(frozen=True)
class FileIdentity:
    """LIVE-session file identity. `path` is the label; (dev, ino) is the identity."""
    path: str          # canonical realpath — for messages only
    dev: int           # ┐ equality is on these two, never on path
    ino: int           # ┘


@dataclass(frozen=True)
class RevisionId:
    """ACROSS-run identity for a cached observation. A different question, a different key."""
    path: str
    content_digest: str    # the file's own bytes
    context_digest: str    # ancestor conftests + fixture origins + the regime
```

The two file identities answer different questions and must not share a type: `(dev, ino)` is
meaningless across runs, and a content digest is meaningless for "is this the same open file."
Conflating them is `109a5db`'s bug in a new spelling **[C]**.

**`reachability.module_name` is deleted in C1, not here — and there is no cycle to dissolve.**
`module_name`'s only callers are `_build_graph` and `reachable_test_paths` **[V]** (verified via
`find_referencing_symbols`), which the walk deletion removes together; deleting it earlier would
break a walk that Phase B keeps. The real `regime.py → reachability.py` dependency is a **one-way**
import of the walk constants `_SKIP_DIRS` / `_pytest_norecursedirs` (`regime.py:37` **[V]**) — not
`module_name`, and not a cycle: `reachability.py` imports only `ast`/`os` **[V]**. It dissolves when
the walk goes (C1). Today the target is named by `oracle_light.importable_module` (`regime.py:38`)
and graph nodes by `module_name` — the §4.6 two-namer split; folding both onto `regime.module` is
part of the C1 deletion and touches **#28**.

## 7. Layer 1 — universe construction **[P]**

```python
# Detective/regime.py — beside resolve_regime, which supplies its only argument

def collection_universe(regime: TestRegime) -> list[str] | None:
    """What this pytest regime would collect. Takes NO target — that is the point.

    Returns the regime's configured roots VERBATIM (directories, or a configured file),
    or None to let pytest use its own defaults. Never a synthesized file list.
    """
```

- **Roots configured** → return them verbatim. pytest's own boundary, walk, `norecursedirs`, and
  conftest resolution.
- **Nothing configured** → return `None`. Absent `testpaths` is valid pytest configuration, not a
  defect: pytest uses rootdir with its own pruning (§4.4). Offer migration from `audit` only when a
  collection problem is **observed**, never pre-emptively.

Never enumerate files as positional arguments (§4.2, **[C]** `226b4a6`).

### What this deletes

| deleted | why it existed | why it is safe |
|---|---|---|
| `_build_graph`, `_imports_of`, `_reaches` | narrow collection by import reachability | §4.1 it does not discriminate; §4.3 it is unsound |
| `module_name` | name graph nodes | §6 `regime.module` is the one producer |
| `_SKIP_DIRS`, `_pytest_norecursedirs`, `is_virtualenv_root` | prune Detective's own walk | §4.4 there is no walk |
| `_ancestor_conftests` | don't name a sibling conftest as a collection target | we never name a conftest |
| `_testpaths_floor` + four give-up branches | degrade safely | nothing left to fail |
| `cli._reachable_paths`'s blanket `except` | never let scoping break a run | no analysis to break |

Archaeology **#22, #25, #26, #27** become preserved *by construction*: the code that could violate
them no longer exists. `within_declared_testpaths` survives, moved to `regime.py`, answering a
regime question rather than a relevance one.

## 8. Layer 2 — priority **[P]**

`route_test_item` unchanged in shape: a total function from an evidence tuple to an ordered code
set, first-true-clause, one-sided. Four wiring changes:

1. **Delete `_route_live_callables`** (§4.5). It is the identity function *and* the only reason
   `static_reach` carries two incompatible denotations — a FILE bit there, a per-ITEM bit in the
   seed router, with the collision acknowledged in a comment (`ci.py:524-529`) rather than
   resolved. Deleting it removes one denotation.
2. **Delete L2's discarded computation** — `relevant_test_files`, `_build_static_impact_map`,
   `_fixture_files_reaching_target`, `discover_tests`.
3. **Return tagged items.** `partition_live_callables` returns three untagged lists, so Detective
   re-derives `_item_body_names` — `inspect.getsource` + `ast.parse` **per item** — a second time
   (`Detective/engine.py:695-697`) to recover a bit Wesker computed at `ci.py:669` and discarded.
   Return `list[tuple[Callable, RouteCode]]`.
4. **Drop `unknown_dynamic`** until something produces it. A stratum nothing can enter is a lens
   voting on an unmeasured input, which this codebase forbids everywhere else.

`caller_reaches` stays **one hop, same module** (§11).

## 9. Layer 3 — observation, and the `FunctionBasis` **[P]**

The per-function value the whole subsystem produces and every consumer reads:

```python
@dataclass(frozen=True)
class FunctionBasis:
    target: str                              # file.py::qualname
    obligations: Obligations                 # L_t, A_t, M_t
    undischargeable: Obligations             # U_t — candidate-equivalent, flagged-unreachable
    admitted: tuple[Witness, ...]            # the basis B_t
    unresolved: tuple[TestId, ...]           # routed, not traced — NOT disjoint
    excluded: tuple[tuple[TestId, str], ...] # only fresh outcome-qualified non-reach, with reason
    action: str                              # complete | trace_next | gap | unresolved  (§1.3)


@dataclass(frozen=True)
class Witness:
    test: TestId
    discharged: Obligations                  # E(τ,t) ⊆ O_t
    warrant: str                             # basis_membership's code
    origin: str                              # intent | characterization | unattributed  (§2.3)
                                             # from the WRITE LEDGER, never a path glob
```

And the pinned pure decision, beside its consumer — the routing block at
`Detective/engine.py:643-706`, per the house rule that the accessor keeps the object handling:

```python
def basis_membership(observed: str, freshness: str, admissibility: str) -> str:
    """Why one test item is, or is not, evidence about the target (pure — pinned).

    A named code, never a bool — these mean different things and must not collapse:

      "proof"     fresh, admissible, covers        — may discharge an obligation
      "routing"   covers, but replayed or inadmissible — orders only, never proves
      "barred"    covers, but its baseline outcome bars it (inert / failing)
      "disjoint"  fresh outcome-qualified non-reach — may be excluded
      "pending"   not observed; the stratum rank is the prior
    """
```

Same shape as `write_disposition` / `line_proof_basis` / `audit_gate_exit`. It is where the
observed-vs-admissible distinction stops being re-derived at each consumer **[C]** (`f3fd42f`).

### Ledger repairs

1. **One key space.** In-memory reach is `TestId`-keyed, on-disk reach fingerprint-keyed, on-disk
   outcomes `TestId`-keyed with a fourth dict as the join table, rejoined at read time **[R-wire]**.
2. **Stamp `provenance='replayed'` unconditionally at rehydration** (§4.6).
3. **Delete `trace_evidence_admissible`**; `trace_admissibility` owns the decision.
4. **Add containment to `_barred`**, and settle on one barred vocabulary (§4.6).
5. **Validate in `load_outcomes`** so the invariant holds by construction.

**There is no repo-wide coverage ledger.** A prior positive observation may accelerate *routing*.
Correctness never depends on accumulating $\mathrm{Cov}$ across the suite. Persistence amortizes a
repo-scale operation; it does not license one.

## 10. Surfaces — the existing commands **[P]**

| layer | command that already owns it | what changes |
|---|---|---|
| 1 · universe | **`regime`** | reports the configured roots it will hand pytest; migration offered only on an observed problem |
| 2 · priority | **`diagnose`** | its `· test routing` line stops flattening a partition and a non-disjoint provenance count into one dict **[R-wire]** |
| 3 · observation | **`audit`** | tests carry their warrant and origin (ℋ/𝒢); minimality is labelled **basis-relative** (§1.4) |

`diagnose` already prints the census — measured live: `· test routing  6 candidate · 939 unknown ·
0 observed-impossible (0 observed)` **[M]**. The work is fixing that line. `--full` / `--json`
expose the per-item warrant, the same tiering `converge` already uses.

## 11. Escalation — routing only **[P]**

The standard path is deliberately shallow: **one-hop, same-module** caller slice. It stays cheap
because it never speculatively pays for depth.

**The deep slice re-ranks; it does not run after exhaustion.** When the widen has traced a
configured number of unknowns without discharging an obligation, the one-hop ordering has proven
uninformative for this target — so a multi-hop, cross-module, distance-ordered backward slice
recomputes the *rank* of the remaining unknowns. It stays inside Layer 2's "may only order" and
adds no mechanism.

**Exactly what it can and cannot change.** It is invoked under budget pressure — which is
precisely the regime where trace order decides which unknowns are reached before the cut — so
"it cannot change a verdict" would be both false and a contradiction of its own purpose:

- **It CAN change `unresolved` → `complete`.** That is what it is for. It can equally leave a run
  `unresolved` where a different rank would have completed.
- **It can NEVER change a completed verdict between `complete` and `gap`.** `gap` requires *every*
  eligible unknown resolved (§1.3), which is order-independent by definition; and the obligations
  discharged by a full traversal are fixed regardless of order. Order matters only under a cut,
  and a cut is `unresolved`, which is never reported as a gap **[C]** (`303289b`).

So the deep slice may change **whether the search completes**; it can never change **what a
completed search concluded**. That is the soundness statement, and it is weaker than the one the
first draft asserted.

**Synthesis residuals are a different design.** `needs_input`, `needs_structure` (#67) and
`needs_fixture` are convergence/input-synthesis concerns, not basis discovery. They share the
principle — *the residual types itself, and each escalation is scoped to only the dimensions it
names* — but they belong in their own document. Mixing them here is what made the first draft's
escalation table incoherent.

---

# Part IV — Implementation

## 12. The invariant ledger

40 invariants recovered from commit archaeology. **These are the safety properties, and the whole
deletion programme is justified by preserving them — so each carries its origin sha.** Read the
commit before touching the slice that claims to preserve it: these repos write the defect verbatim
in the commit body. Repo is Wesker unless marked **[D]**.

| # | invariant | sha | preserved by |
|---|---|---|---|
| 1 | Test identity is the pytest nodeid, never `__name__`; bump the cache schema when the vocabulary changes | `7613afb` | type (§6) |
| 2 | A parametrized case is its own cache key; **every** construction site must stamp it | `8385cc9`, `89aa154` | type (§6) |
| 3 | Target-file identity is canonical (realpath / dev+ino), never a basename | `109a5db` | type (§6) |
| 4 | The live-suite filter canonicalises **both** sides | `226b4a6` | type (§6) |
| 5 | Never hand pytest scoped files as explicit positional args — measured and deliberately declined | `226b4a6` | construction (§7) |
| 6 | An empty static shortlist is not proof of irrelevance; route the live suite before any early return | `e860780` | the Law (§3) |
| 7 | **Selection is one-sided: only positive executed evidence of non-reach may exclude.** *The* risk model | `16c59b4`, reaffirmed `e860780`, `d1d3e15` | the Law (§3) + algebra (§2.1) |
| 8 | Static candidacy is per-TestId, not per-file; a file-peer is kept but never seeds | `d1d3e15` | the Law (§3) |
| 9 | The per-item body scan reads `callable_source`, never the raw wrapper | `d1d3e15` | untouched |
| 10 | A test of a public caller reaches a private target it never names — positive caller stratum, ordered first | `f94c1db` | untouched (§8) |
| 11 | Target-first activates on a caller-only target, never on a reacher-less orphan | `a171809` **[D]** | untouched |
| 12 | The seeded holder is a **per-function fork**; a session baseline is shared | `b7d9c8d` | untouched |
| 13 | Collection identity is a session fact on its own ContextVar, not a baseline field | `b7d9c8d` | untouched |
| 14 | `expand()` fresh-traces the widened batch; the cache is bypassed | `2941d90` | algebra (§2.1) |
| 15 | The widen fires on the **line** axis too; the oracle compares the covered-line union | `9ac0eef` | untouched |
| 16 | **A cut mid-widen is `unresolved`, never a gap** | `303289b` | §1.3 + §11 |
| 17 | The widen is item-incremental and stops on discharge — never capped by a test budget | `3280ebe` | §1.2 |
| 18 | Open obligations read the normalized proof state, never `bool(survivors)` | `3280ebe` | §1.2 |
| 19 | A replayed cache trace is routing, never proof; close the warm false gap by re-observing | `f067d35`, `c07667d` | algebra (§2.1) |
| 20 | After `freshen_proof` splices, re-derive the **entire** scope with fresh containers | `76785f4` | algebra (§2.1) |
| 21 | **Observed impossibility requires a complete, outcome-qualified, context-keyed cell.** Absence ≠ non-reach | `9367516` | the Law (§3) + §2.2 |
| 22 | testpaths is a **scope**, not an augmentation; a scoped collection error never widens | `a6836b7` | construction (§7) |
| 23 | Discovery matches pytest's own `python_files` patterns and honours testpaths-named files | `66f6f07` | construction (§7) |
| 24 | A TOML scalar testpaths is one path, not its characters — split at the single source | `fb867a2` **[D]** | construction (§7) |
| 25 | Prune virtualenvs by the PEP 405 marker; bound collection by testpaths, never a name list | `ecffa0a` **[D]** | construction (§7) |
| 26 | When reachability cannot narrow, return the configured roots — never the whole repo root | `ecffa0a` **[D]** | construction (§7) |
| 27 | Pass only **ancestor** conftests as collection paths; prune shadow trees | `34cc1d6` | construction (§7) |
| 28 | The target's module identity is the regime's, resolved against `project_root`, not the cwd | `0b8440f` **[D]** | type (§6) |
| 29 | The observed (routing) and admissible (proof) coverage views are **two different sets** | `f3fd42f` | the Law (§3) + §9 |
| 30 | A rewritten generated test is re-read, never served from `sys.modules`; the session is told | `65ba33a` | untouched |
| 31 | Containment and cut are different facts; `uncontained` is not spliced away by a re-trace | `15011f4` | §9 repair 4 |
| 32 | Concurrent in-process profiles serialize with an **RLock**, not a Lock | `8cb6539` | untouched |
| 33 | A manifest/collection fact belongs to the exact session that measured it — bind by scope | `c231a1c` | untouched |
| 34 | The verdict cache is keyed on the execution regime and the budgets that produced it | `af10934`, `928600c` **[D]** | algebra (§2.1) |
| 35 | A cached `ProfilingResult` round-trips its tuple **types**, not just its values | `6e3b15f` **[D]** | algebra (§2.1) |
| 36 | One measurement per report: counts and classifications never from two profiles | `7b8ce48` **[D]** | §14 |
| 37 | One nodeid grammar, spoken by every consumer comparing a profile id to a `def` name | `9dd4394` **[D]** | type (§6) |
| 38 | The executable-line denominator names only lines a trace can ever mention | `3efed56` | untouched |
| 39 | A dotted method qualname is looked up under its trailing attribute | `cdb7599` | type (§6) |
| 40 | **Scoping changes which tests run, never the kill matrix — gated by a disposition-exact oracle** | `8ec466a` | A0 |

**#40 gates everything.** `test_scoped_and_unscoped_verdicts_agree` compares only totals, so
killing mutant A instead of B passes it **[C]** (`8ec466a`). The disposition-exact differential
oracle must be green before Phase B and after every slice. Wesker's own commit records that its
soundness bug was *"caught by the oracle, not by inspection"* **[C]** (`c8ee1c0`).

## 13. Build order

Each slice: Serena-probe the wiring → re-confirm every **[R-wire]** claim with
`find_referencing_symbols` **and every [R-exec] claim by re-running its probe** → change → pin the
pure decision **in isolation** → full suite + `uvx ruff@0.14.10` → commit.

### Phase A — the gate

| # | slice | seam | risk |
|---|---|---|---|
| **A0** | Land the disposition-exact differential oracle as a standing gate; confirm green | — | none |

### Phase B — make the current system honest (no deletions yet)

| # | slice | seam | risk | proves |
|---|---|---|---|---|
| **B1** | Land the identity types — `TestId`/`ModuleId` `NewType`s, `FileIdentity`, `RevisionId` — in `regime.py`. **No deletions** (`module_name` waits for C1, §6) | `resolve_regime` | low | §4.6's identity divergence is now *expressible* |
| **B2** | `_reachable_paths` returns a reason-carrying result — `scoped` / `roots(reason)` / `declined(reason)` — not `list \| None` | `_reachable_paths` (32 lines) | low | "declined" and "crashed" stop being one value |
| **B3** | Settle **[?] §2.2**; make the replayed-negative precondition explicit or demote it | `observed_function_reach` | medium | the only cached value that can shrink the search is warranted |

B2 precedes every deletion on purpose: it is 32 lines with one caller and changes no verdict, but
it makes Phase C's risk *observable* — once a decline carries a reason, the ARC measurement can
distinguish "declined" from "narrowed" instead of inferring it.

### Phase C — delete

| # | slice | seam | risk | proves |
|---|---|---|---|---|
| **C1** | **Delete Layer 1's target filtering.** `regime.collection_universe`; roots verbatim; no synthesized file list. Removes the walk (`_build_graph` / `reachable_test_paths` / `module_name`) and folds `oracle_light.importable_module` + `module_name` into `regime.module` (§6, #28) | `reachable_test_paths` | **medium** | ARC e2e: verdict-parity + wall-clock |
| **C2** | Delete §4.7's dead ledger and L2's discarded computation | `discover_test_callables` | low | the identity-function claim, re-confirmed **by execution** |

**C2's gate is a behavioural probe, not a reference sweep.** The `_route_live_callables`
identity-function finding is **[R-exec]**: it came from executing the function directly against
the local Wesker with the production argument values (`static_reach ∈ {item,none}`,
`fixture_reaches ∈ {T,F}`, `caller_reaches=False`, `observed_reach="unseen"`,
`dynamic_uncertain=False`). `find_referencing_symbols` cannot settle it — a single-seam reference
structure is entirely consistent with a non-identity function. Re-run the probe before deleting.

**C1 is the only slice carrying real risk**, and it needs a measurement, not an argument: **ARC
end-to-end** — the sparse repo Layer 1 was built for. The claim under test is that Layer 2's
per-item routing already recovers there what Layer 1's file filter was doing. If it does not, C1
stops and the import graph returns as a Layer-2 **prior** — ordering only, never excluding — which
the Law permits. Every other slice is independent of that outcome.

### Phase D — rebuild around the basis

| # | slice | seam | risk | proves |
|---|---|---|---|---|
| **D1** | `FunctionBasis` + `Witness` + `basis_membership`, pinned in isolation | — | low | the object exists before anything consumes it |
| **D2** | Rewire seed → widen → `next_routing_action` to produce a `FunctionBasis` | `_build_test_scope` | medium | obligations drive termination, not `bool(survivors)` |
| **D3** | Tagged items from `partition_live_callables`; drop the duplicate `_item_body_names` pass; `impossible` leaves the pool, not just the widen list | `partition_live_callables` | low | one parse per item per function |
| **D4** | Ledger repairs 1–5 (§9) | `observed_function_reach` | medium | #19 / #29 hold end to end |
| **D5** | ℋ ⊎ 𝒢 origin attribution on every `Witness` | — | low | intent-grounded vs characterized becomes reportable |

`converge-before-wiring` applies to D1: pin `basis_membership` **before** it is wired into
anything broadly called, or its covering set inflates to suite scale and the pin hangs.

### Phase E — surface

| # | slice | seam | risk |
|---|---|---|---|
| **E1** | `diagnose`'s census stops flattening; `audit` carries warrant + origin and labels minimality basis-relative; `audit --remove` restricted to traced tests; `trace_tier` uses `profile`'s universe | `_build_test_scope` | low |

### Phase F — separate designs

| # | slice |
|---|---|
| **F1** | Deep-slice re-ranking (§11) — routing only |
| **F2** | Synthesis residual routing (`needs_input` / `needs_structure` / `needs_fixture`) — its own document |

## 14. Reviewer's checklist

- **No layer exceeds its permission.** `collection_universe` takes no target and reads no mutant
  or trace. Nothing in Layer 2 returns a filtered set. Only Layer 3 writes `excluded`.
- **No new command, no new module.** If a slice wants either, the layer boundary is wrong.
- **No repo-wide coverage relation.** Correctness never depends on accumulated `Cov`.
- **No bare `except Exception` in the stack.** Every degradation is a named, recorded disposition.
  "Declined", "computed" and "crashed" must never be one value — today they are, at `cli.py:143`,
  `engine.py:706`, `cli.py:3940` **[V]**, and one of those swallows has already hidden a real
  defect **[C]** (`bd6f24e`).
- **`impossible` leaves the pool**, not merely the widen list — today it re-enters through every
  `_tests_for` fallback **[R-exec]**.
- **The empty-seed path never un-scopes.** With zero candidates and a caller-reacher, the seed
  traces nothing, `line_cov` is `{}`, and `_tests_for` degrades to the *full usable set for every
  mutant* — strictly worse than not activating. It also zeroes `inert`, disabling the
  baseline-failing bar `_build_test_scope` calls "the honesty guard" **[R-exec]**.
- **One measurement per report** (#36): counts and classifications never from two profiles.
- **The MCP surface computes the same universe as the CLI.** `mcp_server.py:709` passes neither
  the target module, the import roots, nor the testpaths **[V]**.
