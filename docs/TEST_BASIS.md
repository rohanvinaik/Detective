# The Function Basis — an overhaul of test discovery, scoping, and proof accounting

**Status:** A–E IMPLEMENTED (the Part V gap ledger X1–X6 is closed; see §15–§16). The FunctionBasis
is live as a REPORTING projection, not yet the loop's governor; F0's residual→synthesis dispatch and
"FunctionBasis governs converge" are the remaining work to call this the full Sandwich. Sections that
still read as future tense (Part I–IV design prose) predate the build — the closeout in Part V is the
current state of record.
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
> **2 · No new module. [SETTLED — module count unchanged.]** This is a **rewiring**, never an
> addition. The "−1 module if C1 lands" bet is OFF: the ARC measurement ran, C1 (delete
> `reachability.py`) was REVERTED, and the import closure is load-bearing in the sparse regime as a
> sound eligibility bound (see "The scoping correction"). `reachability.py` STAYS. Everything in
> Phases A, B, D, E and F is sound regardless.
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

**Consequence for the plan. [Soundness + deletions DONE; residual→synthesis OPEN.]** C1 (delete
Layer 1) is **REVERTED**; the pre-C1 sound scoping is restored and `reachability.py` stays. The
corrected C-phase (§13) has three DONE slices: **C1′** fixed reachability's §4.3 soundness hole
(`reach_disposition`, Detective `c9f732c`); **C2** deleted the four genuinely-dead symbols after
grounding proved the doc's ledger mostly stale (Wesker `1c5c9ad`); **C3** short-circuited the
proven-identity live routing path, keeping `_route_live_callables` for the conservative narrowing
(Wesker `1b34e44`). The §4.3 "dynamic-dispatch" hole was already sound (opaque covers it). Still
**OPEN**: **route the un-killed residual to synthesis** (never grind the suite) — Phase F territory.
The Three-Layer Law (§3) is amended:
"only Layer 3 may EXCLUDE (from the certificate)" stands; eligibility for the widen may be soundly
bounded by an over-approximating reachability at Layer 2, because a provably-unreachable test is not
a certificate claim — it is work that provably cannot contribute.

---

# The synthesis floor — a zero-candidate target is pinned by SYNTHESIS, never by a whole-suite trace

**Recorded 2026-08-15, the first EXPLICIT statement of this principle by the project owner. It is a
direct corollary of the sandwich thesis and co-equal with "The scoping correction": the two together
are why Detective never touches the whole suite. It OVERRIDES any path that traces every discovered
test — specifically the `_activate_target_first` "full_baseline" fallback and `_tests_for`'s
`not line_cov → full` degradation (§14).**

**The principle.** The test suite is a **helper and an efficiency boost, never a requirement.** Raw
synthesis of the mutant-complete set is genuinely expensive — several rounds — but a whole-suite
trace usually takes **WAY** longer (the observed pathology: ~1013 tests traced in-process to profile
ONE function, and an intermittent hour-long deadlock when one of those tests blocks outside the
interpreter — see the converge-hang investigation). So the rule is absolute:

> **NEVER trace the whole test suite.** If discovery is sound, a zero- or low-candidate routed subset
> honestly means **there are no reaching tests** — and that is **FINE**: behavior is pinned by
> synthesis alone, with no suite at all. A **leaf orphan** (no routed candidate, no caller-reacher)
> synthesizes from an **EMPTY** baseline; it does not fall back to tracing the hundreds of tests that
> provably cannot reach it.

**Why it is disposition-exact (and keeps the #40 oracle green).** For a *true* orphan, no test
reaches the target, so the whole suite kills **zero** of its mutants — identical to evaluating
against the empty set. `full_baseline` (trace everything) and `synthesize-from-empty` therefore
produce the **same verdict** — every mutant survives → synthesize — so removing the trace changes no
conclusion, only the wall-clock. The equivalence holds **iff orphan detection never false-negatives a
reacher**, the same soundness the over-approximating reachability of "The scoping correction" already
supplies.

**The accepted trade — stated so it is not a silent gap.** A *purely dynamic* reacher — a test that
reaches the target only by reflection, naming it nowhere static and touching it through no fixture
edge — is invisible to routing and *would* be caught by a whole-suite trace. **We accept not finding
it.** Routing by discovery is the contract; a zero-candidate subset is taken as "no tests." This is a
deliberate trade of "catch a reflection-only reacher" for "never whole-suite-trace," and it is
exactly what makes the hour-long converge deadlock structurally impossible rather than merely rarer.
A consumer who needs the reflection-only test found must name it (static reference or fixture), not
rely on an exhaustive trace.

**The measurement/decision gap it closes.** An empty covering set from a *completed scoped trace*
("we traced the routed set and no test covers this line → synthesize") must never render identically
to an empty set from *no trace* ("no data — be safe, run the full set"). `_tests_for` conflated them
(`not line_cov → return usable`, the whole set); the fix names them apart — an authoritatively-scoped
empty baseline returns `[]` (→ all mutants survive → synthesis), only a genuinely-absent baseline
keeps the full fallback.

**Consequence for the build.** `_activate_target_first` gains a `"synthesize"` disposition for a leaf
orphan (was `"full_baseline"`); a leaf orphan is `seed([])` — no trace — and the resolver returns `[]`
so mutants route to the existing "synthesize from scratch" path. Pinned as pure decisions;
disposition-exact under the differential oracle (#40).

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

where $U_t$ is the **undischargeable residue** — every VALUE-undischargeable survivor
(candidate-equivalent, **crash-only**, and manual-equivalent mutants) and lines flagged unreachable.
$U_t$ is reported, never absorbed. The OPEN obligations are the killable and unclassified survivors,
so the basis reads complete-modulo exactly where converge's `functionally_complete` does (review
reconciliation: a crash-only survivor is value-undischargeable — no input pins its value — so it is
$U_t$, not open, even though a crash input distinguishes it).

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

### 2.2 [SUPERSEDED by X1/G1 — a replayed negative NEVER excludes] May a replayed negative exclude?

**Struck. X1/G1 (§15.1) demoted this to "never".** The B3 ruling below let a replayed negative exclude
under a "complete" regime, but the completeness precondition was unattainable in practice:
`test_fingerprint` cannot certify a test's imported-helper closure is unchanged, so a stale negative
could exclude a now-reaching test (a false COMPLETE, reproduced). `observed_function_reach` is now
POSITIVE-ONLY — a replayed non-reach degrades to `unknown` and re-traces, never excludes — matching
the pinned `basis_membership` rule (`replayed non-reach → pending`, never `disjoint`). The B3 admit
decision (`replayed_negative_admission`) was retired. The B3 analysis below is kept for its grounding.

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

### 4.3 [RESOLVED — Detective `c9f732c`] The fixture-only reacher soundness hole

**Fixed.** Reproduced live against local Detective, then closed by COMPLETING the
over-approximation: `reachable_test_paths` now keeps a test iff its own module reaches the target
**OR** an ancestor `conftest.py` does. A conftest that cannot reach the target defines no fixture
that can, so a fixture-only reacher is no longer dropped, and a genuine non-reacher still is. The
decision is the pinned pure function `reach_disposition(module_reaches, fixture_reaches) -> direct |
fixture | unreached` (§5.1, ✓ 6/6). Measured on ARC `serialize_rule` via the **real** regime
(`resolve_regime` → module `src.story.crystallize`, `import_roots=()` — NOT a hand-guessed `('src',)`,
which yields 0/96): 96 in-scope, keep 12 unchanged — **zero over-inclusion**, still narrows 96→13.
Precision (fixture-name + autouse resolution, to drop no-fixture riders under a reaching conftest) is
deferred to Phase F: a precision gain, not a soundness requirement, and premature fixture parsing
would reintroduce the drop-a-reacher risk. The original defect, for the record:

A test whose only path to the target was a **conftest fixture** was silently excluded. The import
graph has no `conftest → test` edge, because pytest *injects* fixtures. Reproduction:
`tests/conftest.py` does `from pkg.mod import quote` and exposes it as a fixture;
`tests/test_via_fixture.py` takes only the fixture and was dropped.

The same failure Wesker already fixed **[C]** (`e860780`), reintroduced one layer up where that
fix could not see it — and in the direction `reachability.py:13-17` says it never goes.

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

### 4.7 The dead ledger **[R-wire — GROUNDED, mostly stale — Wesker `1c5c9ad`]**

**This list was ~9 items; `find_referencing_symbols` on each showed only FOUR were production-dead.**
The C2 gate ("a behavioural probe, not a reference sweep") caught the rest before any deletion — the
same over-reporting the closed-issue audits keep producing. Deleting the live group would have broken
the seams.

**Deleted (Wesker `1c5c9ad`) — genuinely dead, only their own tests referenced them:**
`ci.discover_tests` (a duplicate 3-tier orchestrator) · `ci.split_live_callables` (a thin wrapper
over live `partition_live_callables`) · `ci.live_suite_active` (**zero** references — a spawn-safety
predicate never wired; the real guard lives in `Detective.engine.profile`) ·
`line_coverage.trace_evidence_admissible` (the #29 drift-hazard second admissibility impl —
`trace_admissibility` is the live owner).

**NOT dead — the doc was stale, these are LIVE (or the claim was already fixed):**
`ci.route_admits(conservative=True)` is called by `_route_live_callables` and is a real, test-covered
narrowing (§8) · `unknown_dynamic` — **no such symbol exists** (already resolved) ·
`_is_test_filename(patterns=…)` — `patterns` **is** passed at `_discover_all_test_files` (bug already
fixed) · `run_function_converged`'s `widen_tests` — the function is LIVE and exported; the "dead
internal widen" sub-claim was not re-confirmed and is left untouched.

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
| `within_declared_testpaths` | `reachability.py` (STAYS — C1 reverted, §"scoping correction") | 16/16 |
| `reach_disposition` | `reachability.py` (NEW — §4.3 fix, `c9f732c`) | 6/6 |
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

**`reachability.module_name` STAYS — C1 is reverted (see "The scoping correction").** It was to be
deleted with the walk in C1; that reversion keeps the walk, so `module_name` keeps naming graph
nodes. Its only callers are `_build_graph` and `reachable_test_paths` **[V]** (verified via
`find_referencing_symbols`). The `regime.py → reachability.py` dependency remains a **one-way**
import of the walk constants `_SKIP_DIRS` / `_pytest_norecursedirs` — not a cycle: `reachability.py`
imports only `ast`/`os` **[V]**. The §4.6 two-namer split (target named by
`oracle_light.importable_module`, graph nodes by `module_name`) is therefore NOT folded here — it
would have ridden the C1 deletion, and touches **#28**; it is now a standalone follow-up if pursued.

## 7. Layer 1 — universe construction **[P]** — ⚠️ STRUCK (C1 reverted)

**Do not build `collection_universe` or the deletions below.** This whole section is the delete-Layer-1
plan; C1 was measured and REVERTED (see "The scoping correction" and §13 Phase C). `reachability.py`
and its walk STAY; the corrected work was C1′/C2/C3 (§13), all done. Kept for its reasoning only.

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

1. **[DONE — Wesker `1b34e44`, refined by the `[R-exec]` probe] Short-circuit the proven-identity
   path — do NOT delete `_route_live_callables`.** The probe (executed, not read) showed it is the
   identity function **only at `conservative=False`** (every production call): all four routes
   `static_reach×fixture` over `{item,none}×{T,F}` are admitted, so it returns `live` verbatim. At
   `conservative=True` it genuinely drops `unknown_no_path` — a real, test-covered narrowing — so
   deleting it (the original plan) would remove a capability. Instead, `discover_test_callables` now
   short-circuits `if live is not None and not conservative: return live` **before** computing
   `scoped`, skipping the `relevant_test_files` impact map the identity discarded on every live call
   (§4.5 waste). Behavior-preserving in all cases. **Not done:** the `static_reach` FILE-vs-item
   denotation collision survives with the function — it is documented and intentional, and removing
   it was contingent on a deletion the grounding does not support.
2. **NOT a discarded computation — these are LIVE.** `relevant_test_files`,
   `_build_static_impact_map`, `_fixture_files_reaching_target` feed `discover_test_callables`'s
   non-live backends and its conservative router; only `discover_tests` (a genuine dead duplicate)
   was deleted (§4.7, C2). The impact map is no longer *discarded* on the live path — it is no longer
   *computed* there (point 1).
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

### Phase C — soundness + delete (SUPERSEDES the delete-Layer-1 plan; see "The scoping correction")

C1 (delete Layer 1) was built, measured on ARC, and **REVERTED**: sound scoping is an ELIGIBILITY
BOUND, not a forbidden exclusion. The corrected C-phase is **fix reachability's soundness**, then
**delete only what grounding proves dead** — all three slices below are DONE.

| # | slice | seam | status |
|---|---|---|---|
| **C1′** | **Fix reachability's §4.3 soundness hole** (was: delete Layer 1). A fixture-only reacher is kept via the pinned `reach_disposition`; sound over-approximation, measured 96→13 on ARC with **zero** over-inclusion | `reachable_test_paths` | ✅ Detective `c9f732c` |
| **C2** | Delete only the FOUR genuinely-dead symbols §4.7 grounding confirmed (`discover_tests`, `split_live_callables`, `live_suite_active`, `trace_evidence_admissible`) — NOT the doc's stale ~9-item list, and NOT the live L2 computation | `discover_test_callables` | ✅ Wesker `1c5c9ad` |
| **C3** | Short-circuit the proven-identity live routing path (skip the discarded impact map); keep `_route_live_callables` for the `conservative=True` narrowing | `discover_test_callables` | ✅ Wesker `1b34e44` |

**The `[R-exec]` probe governed C2/C3, not a reference sweep.** `_route_live_callables` is the
identity function **only at `conservative=False`** (executed against local Wesker: all four
`static_reach×fixture` routes admit; `conservative=True` drops `unknown_no_path`). So it was
short-circuited, not deleted — deletion would have removed a test-covered narrowing. And §4.7's
`find_referencing_symbols` sweep proved most of the "dead ledger" LIVE before any deletion.

**What C1's reversion settled:** deleting Layer 1 held verdict-parity but blew the widen's
eligible-unknown pool **12→423**, and the residual obligations were undischargeable by ANY suite
test. The recovery is the sound eligibility bound (C1′) plus **drop-to-synthesis for the residual**
(the remaining C-phase work, still open), not an ordering-only prior. `module_name`,
`within_declared_testpaths`, `_SKIP_DIRS`, `_pytest_norecursedirs`, `is_virtualenv_root`,
`_ancestor_conftests` all STAY in `reachability.py` — the C1 deletion that would have moved or
removed them is reverted.

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

---

# Part V — Gap closeout (A–E) and what F requires

Written after A–E landed and were reviewed. Every claim below was **re-verified in this repo**:
`find_referencing_symbols` for the wiring, a built synthetic repo for each soundness claim, and a
cross-checking reconcile pass that settled nine contradictions between independent surveys. Where a
survey and the code disagreed, the code won and the survey line is not reproduced.

## 15. The verified gap ledger

| # | gap | class | verified |
|---|---|---|---|
| **G1** | A replayed negative excludes a real reacher: `test_fingerprint` omits imported helper modules — the third bullet of Wesker #20's own unkeyed list, never closed | **soundness — false COMPLETE** | **[M] reproduced** |
| **G2** | `pytest_plugins` is unmodelled, so a conftest reaching the target only through a declared plugin scores `conftest_reach=False` and drops the fixture-only test | **soundness — lost kill** | **[M] reproduced, fix verified** |
| **G3** | `function_basis`'s three obligation sources are all wrong, and its **signature cannot reach the right ones** | semantics | **[V]** |
| **G4** | Nothing in production calls `function_basis`; `basis_membership` has no consumer; `BasisWitness` is never instantiated | wiring (D2) | **[V]** |
| **G5** | `witness_origin_of` pins `edited=False`; no content digest is recorded at write time | wiring (D5) | **[V]** `certify.py:695` |
| **G6** | `diagnose`'s census flattens; **`audit` minimizes on the RAW union while converge minimizes on the ADMISSIBLE one**; "minimal" is unlabelled | surface (E1) | **[V]** |
| **G7** | `ScopeMap`'s documented routing invariant is **false against the code** | correctness of a stated invariant | **[V]** `scope.py:92-94` |

### 15.1 G1 — reproduced, and the seam is simpler than expected

```
fingerprint BEFORE helper edit: d8e3aaf6b6fc2509
fingerprint AFTER  helper edit: d8e3aaf6b6fc2509     ← identical
```

§2.2/B3 ruled for option (a) and closed two residuals (config-file content; Hypothesis seed via the
pinned `replayed_negative_admission`). That audit concluded *"only two residuals were real."*
**A third was real and is on #20's own list** — *"helper modules/imported constants."*
`regime_digest` keys plugins, conftests, config and import mode; `test_fingerprint` keys the test's
own source, fixture origins, and ancestor conftests. An ordinary imported module is in neither.

**The reconcile pass found the seam is narrower than the design assumed.** `trace_cache.py:392` is
the **sole producer** of a routing negative and it is **disk-only** — `observed_function_reach`
builds only from `load(...)` and `load_outcomes(...)`. Therefore:

> **Every negative `route_test_item` can see is already a replay.** The "fresh negative may
> exclude" row of §2.1 is *vacuous in production* — there is no fresh negative to admit.

So `ci.py:406-407` (`observed == "not_reached" → impossible_observed`) is, today, exclusively the
unsound case. Two consequences:

- **X1 is a smaller change than scoped**: demote at the single consumer, or close the fingerprint.
- **`basis_membership` already encodes the correct rule.** `Detective/engine.py:493-501`:
  `if observed == "non_reach" and freshness == "fresh": return "disjoint"` else `"pending"`. The
  right rule is written and pinned in the **unwired** object while the **wired** path does the
  unsound thing. G4 is therefore not merely architectural — wiring it is part of G1's fix.

### 15.2 G2 — reproduced, fix verified

```
pytest itself:          2 passed                     (collects and runs both)
reachable_test_paths -> conftest.py, test_direct.py  ← test_via_plugin.py DROPPED
WITH FIX ->             conftest.py, test_direct.py, test_via_plugin.py
```

`_DYNAMIC` already lists `pytest_plugins` (`reachability.py:26`) but is consulted only against
**import-statement** names (`:119`, `:137`); `pytest_plugins` is a module-level list assignment, so
the entry is dead as written. Marking such a module **opaque** restores the test — the module's own
existing escape hatch, ~4 lines, no plugin resolution modelled. This is exactly what "The scoping
correction" prescribes: *completing* the over-approximation, not deleting the analysis.

### 15.3 G3 — larger than the review found

`basis_action` (`engine.py:503`) is correct and pinned; `has_open_obligations` is pinned. **Both
decisions are right and the guarantee is hollow, because the accessor feeding them is wrong** —
*"pin the decision, never ask what feeds it."* Four defects, not three:

| # | now | must be |
|---|---|---|
| 1 | covered lines from raw `result.line_coverage` | `admissible_proof_coverage(result)` — `converge.py:1139`, *"the ONE place the choice is made, so converge and audit cannot drift — and that drift WAS the #59 bug"*. Import **inside the function body**, as `audit.py:285` does (converge imports engine at module scope) |
| 2 | `mutation_dims = kill_matrix.keys()` | `kill_matrix` keys are `f"{mutant_id}: {desc}"` — a key space **disjoint from `mutant_id`**, holding only killed-**and-attributed** mutants. Build $M_t$ from `killed_records + survivor_records` keyed on `mutant_id` |
| 3 | `undischargeable` = uncovered lines | $U_t$ line half = `manually_unreachable` from `classify_missing_lines(project_root, func_key, func_node, missing, covered)` (`line_flags.py:242`), `covered` from the **admissible** map — the invariant both existing consumers keep (`audit.py:309`, `converge.py:1941`) |
| 4 | `total_equivalent` for the equivalent count | **structurally 0 on every result Detective returns.** Only `run_function_converged` sets it (`Wesker/engine.py:6682`); Detective calls `run_function_profiling`. Source from `SurvivorReport.candidate_equivalent` |

**And the signature cannot reach any of them.** `function_basis(result, validity)` has no
`project_root`, no `func_key`, no AST node — but `classify_missing_lines` needs three,
`classify_survivors` needs three, and the mutant universe needs the node. **G3 is a signature
change**, which is why it must precede G4 rather than accompany it.

Reuse, do not invent: `converge.py:1036-1089` (`_self_owned_obligation_ids`) already assembles
line + arc + kill obligation ids from one result, and reaches arcs through `trace_evidence` +
`getattr(ev, "admissible", False)` — **not** through `admissible_arc_union`, which has zero
production consumers.

### 15.4 Items the surveys corrected in the design's favour

- **`partition_live_callables` already returns tagged `(callable, code)` pairs** (`ci.py:638-642`).
  §8's "return tagged items" **shipped**; Detective throws the tag away at `engine.py:862`
  (`_widen_tests = [c for c, _ in _unknowns]`). One Detective-side line, no Wesker API change.
- **`_impossible_ids` removes tests from the POOL** (`engine.py:845` → `:881`), not merely the
  widen — confirming the checklist item, and it is what makes **G7** true: `tests_discovered` is
  computed from the impossible-filtered list (`Wesker/engine.py:5963`), so
  `candidate + unknown + impossible == tests_discovered` is false. Correct the docstring or the
  denominator; any surface printing it inherits the error.
- **The `· test routing` render is wrong, not merely flat** (`cli.py:253-265`): it reads as
  "N impossible, of which M observed", but `impossible` is populated **solely** by `ci.py:406-407`,
  so impossible ⊆ observed and M ≥ N by construction.

## 16. Closeout order

**Soundness before architecture; correct the assembler before wiring it.**

| slice | closes | seam | risk |
|---|---|---|---|
| **X1** | **G1** — the helper-closure fingerprint, or demote at `ci.py:406-407` | `trace_cache.py:392` → `ci.py:406` | medium |
| **X2** | **G2** — `pytest_plugins` ⇒ opaque | `reachability._imports_of` | low |
| **X3** | **G3** — assembler semantics **and signature**, still unwired | `engine.py:585-615` | medium |
| **X4** | **G4** — attach a basis at `profile()`'s two return sites; wire `diagnose`/`audit`/converge | `engine.py:776` and `:913-921` | medium |
| **X5** | **G5** — content digest at `certify._write` (sole writer, `:761-763`; source arrives ruff-formatted) | `certify.py:695` | low |
| **X6** | **G6 + G7** — one minimize basis; census render; `ScopeMap` invariant | `audit.py:280`, `cli.py:253` | low |

X1 and X2 close live soundness holes and are independent of everything else.

**X4's attach seam is already precedented.** `engine.py:913` computes
`_validity = normalize_validity(result)` and **discards it** after the cache-admission check — and
the house pattern for attaching Detective-side state to a Wesker result already exists
(`result.test_routing = _routing_counts`, `engine.py:897`; `hit.served_from_cache = True`). So a
basis can reach production without touching 13 callers.

## 17. What Phase F requires

### F0 — route the un-killed residual to synthesis (highest value)

"The scoping correction" names this as the open half of the core purpose. The ARC measurement is
decisive: `serialize_rule`'s 6 residual obligations are **undischargeable by any suite test**, so
no widening or re-ranking reaches them — only synthesis does. Blocked on X3/X4 for the obligation
signal.

**[B0 LANDED — Detective `49b6ae0`; the TRACTABLE half.]** With X3/X4 shipped the obligation signal
exists, and the active search is built for the case synthesis *can* reach. A `deep_structural`
(worklist/fixpoint) target's candidate-equivalent residual is retried over a fixed CROSS-REFERENTIAL
topology library — index-valid adjacency lists (`_ADJACENCY_TOPOLOGIES`) whose inner integers point
back into the outer list, the content the scalar and length-variant grids never construct.
Grounding corrected the plan: the gap is cross-referential *content*, not nesting *depth*
(`_seq_length_variants` already builds shallow nested lists). The retry is rescue-style (fires only
on a persisting residual), **positive-only** (a topology can only *prove* a kill, never erase one, so
no false COMPLETE), and world-effects + `#31`-wall gated. Gate: `structural_retry_gate` (pure,
truth-table pinned). Measured end-to-end on a worklist target: 12→14 kills, 2→0 candidate-equivalent
residual, the net kills witnessed by `[[1, 2], [2], []]`.

**[B1 GUARD-DIRECTED LANDED — the SECOND tractable increment.]** The reachability signal (RIP-R, §6 door
2) now identifies an unreached candidate-equivalent — one whose mutated line the pool never executed — and
B1 reaches it by the branch's OWN guard: a survivor behind a SIMPLE comparison guard (`len(x) > 5`,
`x == 42`) gets a guard-satisfying input synthesized off the AST (`_guard_directed_inputs` /
`guard_comparison_target` / `guard_retry_gate`, truth-table pinned), retried positive-only through the same
`_classify_pool`. Measured on a `len(items) > 5` target: the unreached VALUE survivors go from
candidate-equivalent to KILLED, leaving only the reached-but-not-propagated residual. The generalization of
B0 from a fixed topology library to the guard the branch itself declares.

**Still open — the intractable core.** GENERAL cross-referential / DIFFERENTIAL domain-object synthesis:
`serialize_rule`'s residuals need a *differentiating* `Relation` (a domain object, `--input`-inexpressible)
that no guard names and no synthesis over the input LANGUAGE reaches — it routes to the door-3 fixture
caveat (§6), NOT a kill. B0 + B1 are bounded down-payments; the differential domain-object reach is the open
synthesis problem, deliberately NOT claimed.

### F1 — the deep-slice re-rank

**Correction: F1 is NOT blocked on X4.** The obligation signals are already local to the widen loop
head (`Wesker/engine.py:5678-5685`: `bool(_survivor_mutants) or _lines_incomplete`), so an
in-loop progress counter needs nothing from the basis.

The seams are exact:

- **trigger** — the widen pop, `Wesker/engine.py:5689`: `_batch, _remaining_widen =
  _remaining_widen[:1], _remaining_widen[1:]`. Never re-sorted, so widen order *is* the caller's
  list order.
- **re-rank** — `ci.py:640`, `key=lambda r: _unknown_stratum_rank(r[0])`, a **stable** sort. A
  secondary key therefore cannot cross a stratum boundary **by construction**, so "may only order,
  never exclude" holds structurally rather than by discipline.

Scope it honestly: F1 cannot recover a large eligible pool ("ordering cannot reduce a sound
exhaustion"). Its value is turning some `unresolved` runs into `complete` under budget pressure.

### F2 — synthesis residual routing

Its prerequisites are about the *residual*, not the basis: type the residual (today one
undifferentiated `I_solve` bucket, which is what makes a killable-but-unsynthesized survivor
indistinguishable from a genuine equivalent), then #67's structural detector as the shared gate,
then the escalation dispatch.

One live defect found in passing: **the structural advisory reaches neither surface that invites a
flag.** `structural_difficulty` (`converge.py:2005`) is read once, at `cli.py:1659`, but the
default terminal path is `_format_converge_terse` (`cli.py:4897`), which never calls it — and
`converge_next_action` does not consume it. So the caution built to prevent a false equivalence
flag is absent from the surface that invites one.

## 18. Open questions — flag, never guess

The reconcile pass surfaced twelve. The five that gate a slice:

1. **The $M_t$ denominator.** `estimate_universe_size` sums mutation *targets*;
   `len(generate_mutants(...))` counts *applied* transforms. Different numbers. — **gates X3**
2. **Is the mutant universe stable enough to be a denominator at all?** `validity.py:197-199`
   stamps `approximate:mutant_universe` on every in-process run, and a measured 133-vs-140
   scored-count drift is on record. If the denominator is approximate, an obligation *count* is
   too. — **gates X3**
3. **Which basis should `audit`'s minimal cover use** — admissible (as converge does) or
   foreign-stripped raw (as audit does)? Two live divergent behaviours; the code does not settle
   intent. — **gates X6**
4. **Should the arc axis be populated at all?** Arcs are opt-in (`trace_evidence.py:85-88`,
   *"it doubles the hot callback"*), so `admissible_arc_union` is empty on a normal run and an arc
   obligation would read **vacuously complete**. — **gates X3**, and it touches §1.2's $O_t$
5. **Where a generated-file content digest lives** (header line / `pins.json` / sidecar) and how a
   *missing* record is classified. All three options have named defects. — **gates X5**

The remaining seven — including whether `run_function_converged`'s widen needs the same treatment,
whether `_content_mutant_id` folds source positions into the digest, and the `uv.lock` ordering if
a basis field is added to Wesker's `ProfilingResult` — are recorded in the run journal.
