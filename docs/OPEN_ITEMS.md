# Open items — the single index

Written 2026-09-09, at the close of the doctor/ledger build. **This file is the index; the linked
sections are the detail.** Before this, open items lived in five places (`DOCTOR.md` §7/§11,
`INVOCATION_LEDGER.md` §7, `CORRECTNESS_REPAIRS_2026-09-08.md` §S10b/§R5.1/U1, and two GitHub
issues) with nothing tying them together.

> **Read this before the design docs, not after.** Those documents were written to GUIDE work that
> has since landed, which makes them anti-correlated with current truth wherever they describe a
> defect — a note authored to be made false is not merely stale, it MISINFORMS. Every row below was
> checked against current source on 2026-09-09. Where a design doc still says something this file
> contradicts, this file wins and the doc has drifted.

---

## 1. FOUNDER CALLS — decisions, not work

Nothing here is blocked on implementation. Each is a question only the founder has standing to
answer, and each is cheap to act on once answered.

| # | Question | Where | Why it is a call and not a task |
|---|---|---|---|
| ~~**D1**~~ | ~~strict pre-emption~~ | | **RULED AND BUILT 2026-09-09: WITHHOLD.** §4's literal reading. A taste verdict measured through a live setup fault is a measurement of the ENVIRONMENT, and printing it under a warning still leaves the reader free to act on it — which is the unreliability the mix exists to NAME rather than decorate. Exit 2, the same code `doctor` returns for the same finding. `--json` exempt: a parsed contract must not silently change shape. |
| ~~**D2**~~ | The cache guard **skips more often than it runs**. | [`CORRECTNESS_REPAIRS` §S10b](CORRECTNESS_REPAIRS_2026-09-08.md) | **CLOSED 2026-09-09 — MEASURED, and the target is not the variable.** The ruling said to find a target that reliably admits; measurement says the current one already does. Isolated: passes 3/3. A controlled replica of the `built` fixture under real full-suite load: correct on 8/8 probes, `trace_truncated=0` throughout. One skip in one full-suite run — so S10b's *"skips more often than it runs"* no longer holds; it is now rare and intermittent, and not attributable to the target. The ruling's own escape clause applies: that finding is the answer. What WAS still broken is that the skip named two possible causes and could not tell them apart, making each occurrence a dot in the log — the same defect one level up from the one S10b found. `ScopeMap` now carries the measurement's `cut_reasons` (the `load_failure` pattern again: a consumer cannot report a fact the type does not define), so the guard says which cause fired, with a test per branch. |
| ~~**D3**~~ | ~~"writes nothing" copy~~ | | **RULED AND BUILT 2026-09-09: "writes nothing to your project".** 17 sites. Machine-facing `note` fields and terse chips use "writes no project files" — the same claim, fewer characters, where the long form did not fit. |
| **D4** | Does `modulo N unproven-equivalent` **assert a frontier it has not established**? | [`CORRECTNESS_REPAIRS` §R5.1 / §R5b](CORRECTNESS_REPAIRS_2026-09-08.md) | **RE-FRAMED 2026-09-09 — the old wording here ("should the search try un-exercised branches?") was R5.1's, and §R5b explicitly supersedes it:** *"the gap is not 'un-exercised branches' — it is the witness search under-searching a domain it can fully express."* Now **three for three**: `outcome_disposition` 24/28 → 28/28 on four hand inputs; `suite_state_comparison` 7/7 first try; **`same_recorded_state` 23/45 → 42/45**, 18 of 22 "unproven-equivalents" killed by obvious boundary probes — and that third instance is a DICT domain, so the finding is not confined to primitives. The DONE block says the residual *"cannot be distinguished by any input Detective found — whether it is truly equivalent is UNDECIDABLE in general"*, which blurs search budget with Rice. The wording half is explicitly **not** a founder call (§R5); the search half is. This is the only open item where the tool may assert more than it established. |
| ~~**D5**~~ | **U1** — un-evaluable universe: REFUSE or Incomplete? | [`CORRECTNESS_REPAIRS` §R5 / pabkit ledger](CORRECTNESS_REPAIRS_2026-09-08.md) | **RULED 2026-09-09 ("it DEPENDS ON WHY" — §2a), then found ALREADY BUILT and now PINNED.** Grounding it against source rather than against the note: `certificate_standing` refuses on ANY cut reason via the absorbing `admits_certificate`, and all four structural causes ARE cut reasons — R1 added `target_load_failed`, S13 split the three mutant-phase ones, §MI made them readable and routed `ungateable` to `measurement_invalid`. U1 was filed before that wave. Evidence from `tests/detective/certificates.json`, not reasoning: `repair_measurement_route` and `measurement_cut_reasons` both stand `ungateable` carrying `cut_reasons: ["mutant_not_entered"]`, while `classify_target` stands `incomplete` with none — both rows of the ruling's table, live. What was missing was a GUARD; `tests/test_unevaluable_universe_intent.py` is it. No new standing was needed, which is why §2a's "do NOT extend `admits_certificate`" pointed the right way. |

### 2a. D5's ruling, in full — because the distinction IS the decision

> **It depends on WHY it was un-evaluable. Refuse when the cause is STRUCTURAL; stay Incomplete when
> the universe was genuinely empty of killable mutants.**

Those are two different facts and collapsing them is the defect this project keeps finding:

| cause | verdict | why |
|---|---|---|
| the module would not import; no mutant was installed; no test entered one | **REFUSE** | nothing was observed. A 0-kill here is BLINDNESS, not a result, and the counts describe an empty observation. `target_load_failed` already refuses on exactly this reasoning. |
| the universe genuinely held no killable mutants | **Incomplete** | something WAS measured and it found nothing to pin. That is a real, honest answer about the code. |

The vocabulary to tell them apart already exists and did not when U1 was filed: S13 split the
three mutant-phase reasons, §MI made them readable from the certificate, and S14 routes them.
`validity.CUT_REASONS` membership is very close to the structural/empty line already — the build is
mostly deciding which reasons are on which side and threading one more standing through
`certificate_standing`, NOT inventing a signal.

**Do not build this by extending `admits_certificate`.** The absorbing rule is deliberately
absorbing; a third state wants its own place, the way `measurement_invalid` did in §MI.

---

## 2. BOUNDED WORK — specified, not started

| # | Item | Where | Notes |
|---|---|---|---|
| ~~**W1**~~ | `outcome` propagation for the remaining verbs. | [`INVOCATION_LEDGER` §10](INVOCATION_LEDGER.md) | **CLOSED 2026-09-09 by a CRITERION, not by wiring eleven sites.** `outcome` earns its place where a verb's named ending is not recoverable from its exit code AND the verb issues an instruction an operator would repeat. Three verbs met it and are wired — `verify-rewrite` (7 verdicts → 4 codes), `decompose` (6 endings → 3, and the two sharing exit 3 have opposite remedies), `regime` (every conflict kind → 2). The other eight fail the SECOND half: five taste verbs are advisory reads whose pre-emption the signpost already handles, and `receipt`/`flag`/`purge` are one-shot acts whose ending IS their exit code. A reason, recorded, rather than a TODO. |
| ~~**W2**~~ | Issue **#68(a)** — recursive, import-collecting constructor emitter for nested-object dataclass fields. | [GH #68](https://github.com/rohanvinaik/Detective/issues/68) | **ALREADY BUILT — this row was stale.** Landed 2026-08-25 (`12b7cfe` / `904e191`); `engine._as_domain_source` walks the instance via `_domain_constructor_imports` and gates on `domain_import_disposition`, which is the import-name-collision risk the issue named. VERIFIED by driving it 2026-09-09: `Outer(child=Inner(n=3), label='x')` renders with BOTH imports unioned, and the flat case is unaffected. `MEMORY.md` recorded this on 2026-08-25 and the index never caught up — the same provenance inversion as W10 and D5. **The founder may want to close #68(a) on the issue itself; issue closure is theirs.** |
| ~~**W3**~~ | Issue **#70** — BLAS last-ULP drift makes golden float captures platform-specific. | [GH #70](https://github.com/rohanvinaik/Detective/issues/70) | **CLOSED 2026-09-09 — founder ruled the issue's OPTION 2: scope the claim, do not weaken it.** No tolerance, no approximate equality; the pin stays exact and the generated suite's header states what it is exact ABOUT, so a mismatch elsewhere reads as a different platform before a regression. Stamped only when the TARGET'S OWN imports reach a numeric backend AND a golden carries a float — the first implementation asked whether one was loaded in the process, which stamped a pure-Python function because a sibling generated test had imported numpy. Driven both ways. Pins: `golden_observation_scope` ✓ 5/5, `observation_stamp` ✓ 9/9, `float_bearing` ✓ 25/28. **Issue closure on GitHub is the founder's.** |

### 2b. The tail this index did not carry — folded in 2026-09-09

Every row below was written down in a ledger *"recorded so they are not silently dropped"* and then
not indexed, because this file was scoped to the doctor/ledger wave's residual and the older ledgers
predate it. Found by sweeping every `.md` in the repo for open markers rather than by remembering.

| # | Item | Where | State |
|---|---|---|---|
| ~~**W7**~~ | The **load-failure exit-code contract**. | `CORRECTNESS_REPAIRS` | **CLOSED 2026-09-09 — measured, then chosen and PINNED.** converge `3`, `audit --check` `1`, bare `audit` `0`, `diagnose` `0`; already coherent, and nothing guarded it. `tests/test_exit_code_contract_intent.py`, including the rule beneath the codes: a verb may exit 0 here only because it NAMES the cause. |
| **W8** | **Regression case 3** — "repairing the import allows progress". Untested; needs a second venv carrying jax+funcy, because `ab/.venv-det` must stay deps-absent — that absence IS the repro. | `CORRECTNESS_REPAIRS` | The one item that is **infrastructure, not code**, and the only engineering gap that cannot be closed by editing this repo. |
| ~~**W9**~~ | **Regression case 5** — `verify-rewrite` under a target-load failure. | `CORRECTNESS_REPAIRS` §R3 | **CLOSED 2026-09-09 — VERIFIED, and it was a verification gap rather than a code gap.** Staged end to end (receipt over a healthy module → break its import → verify-rewrite): it ABSTAINs and the note surfaces *"the live original could not be loaded: ModuleNotFoundError…"*. R2b's repair did reach it — `rewrite_classification_status` consumes `load_failed` at `rewrite.py:606` — so R3's "sound but mute" is now sound and speaking. |
| ~~**W10**~~ | **R0's stated residual** — the probe was exhaustive over tuple-element SWAPs, not every SWAP form, and the 40→48 universe difference is unaccounted for. | `CORRECTNESS_REPAIRS` §R0 | **CLOSED 2026-09-09 as NOT RE-ESTABLISHABLE, and it never carried R0's conclusion.** R0 concluded "fixed, not suppressed" from a probe that hand-built the non-equivalent SWAPs and ran the REAL suite against each — a measurement independent of which mutant IDs the arms happened to assign. Re-deriving the ID mapping and the universe delta would require reconstructing the pre-wave arm, which has not existed since `5324b7b` landed 20+ commits ago. Recorded as unmeasurable-now with the blocker named, rather than left reading as work someone could pick up. |
| **W11** | The **pabkit queue**: the count-noise label, the trace-cache body-digest hypothesis, U4 (a written test that kills 0), U5 ("proposed removals: your own test"), the exception-message-only CLI copy. | `CORRECTNESS_REPAIRS` "Not in scope here" | Small, individually cheap, never indexed. |
| **W12** | **TEST_BASIS Phase C: "drop-to-synthesis for the residual"** — named as *"the remaining C-phase work, still open"*. C1′/C2/C3 are all ✅; this one is not. | [`TEST_BASIS`](TEST_BASIS.md) Phase C | The largest of the tail, and arguably research rather than bounded work — see §3. |

**Deferred with a reason, and NOT engineering debt** — recorded here only so a future sweep does not
re-find them as gaps: `ARCHITECTURE.md`:585 (σ-based spec-completeness ETA, "not blocking");
`PARSIMONY_ADVISORY.md`:231 (duplication and import-layering axes) and :74 (repo-scale axes, which
are **Uroboros's**, not Detective's — a scope boundary, not a backlog).

---

## 3. RESEARCH — no bounded shape yet

| # | Item | Where |
|---|---|---|
| **R1** | Issue **#68(b)** — the genuinely irreducible representation residual: a non-introspectable object has no field to vary and no constructor `repr` to render. Both partial directions have a rendering blocker. | [GH #68](https://github.com/rohanvinaik/Detective/issues/68) |
| **R2** | The ledger's retention policy is a **placeholder**. 5 MB oldest-evicted is a raw-ledger policy that treats every entry as equally worth keeping; the better system is meaningfulness-focused (a spiral's three identical entries are ONE event; the run where the interpreter changed is worth more than the fifty around it). Story-understanding over a data geometry — the natural bridge to the inference work past the boundary of knowability. | [`INVOCATION_LEDGER` §4](INVOCATION_LEDGER.md) |

**R2 is deferred on purpose, not overlooked.** The 5 MB cap was chosen to be generous enough that no
data the future design would want is being thrown away in the meantime.

---

## 4. WHAT IS CLOSED — do not re-open these

Listed because the session's own notes were wrong about several of them, and a future reader
grounding off a design doc alone would re-litigate settled ground.

| Item | Status |
|---|---|
| **doctor** | BUILT — green · yellow · red · the verb · the signpost · all four superadditive products. `DOCTOR.md` §8–§12. |
| **The invocation ledger** | BUILT — persistence shell, the one `try/finally` call site, `outcome` propagation for four verbs, `purge --prune`. `INVOCATION_LEDGER.md` §8–§11. |
| **W4 — `reproducibility_verdict`** | **WIRED 2026-09-09** (`converge.py:2317`). It was called AROUND: the call site computed `set(a) == set(b)` inline and passed a bool. The severity was that `test_the_verdict_is_set_equality_over_the_survivor_ids` — the intent guard for exactly that property — pointed at the orphan, so order- or duplicate-sensitivity could have been introduced at the live expression with the test still green. |
| **W5 — `structural_residual_handback`** | **CLOSED 2026-09-09 as BY DESIGN, on a reason that predated the finding.** `F2_RESIDUAL_TYPING.md` §4 recorded on 2026-08-25 that it is redundant and reserved. Confirmed independently: `residual_disposition` returns `fixture_residual` **before** the structural gate, so `structural_residual` already implies `inputs_expressible` and the `structural_fixture` branch is unreachable from production. I filed it as a gap because I had not read F2 — the third time this session that a design doc already held the answer. |
| **W6 — `module_identity_conflicts`** | **CLOSED 2026-09-09 by DELETING it.** It was a cross-repo DUPLICATE of `Wesker/session_manifest.py::conflicting_module_names`, which owns the data (`PytestSessionManifest.module_origins`), is consumed at `Wesker/session_manifest.py:183`, and whose standing (`collection_identity_standing`) is consumed at `Wesker/engine.py:4949`. Detective never touched the manifest. `TEST_BASIS.md` §4.8 names this exact class: *"each is still a MIRROR… every mirror this overhaul deletes is one prediction replaced by that observation."* `Detective/session_manifest.py` held nothing else, so the module went with it. |
| **The consumption question** | **BUILT 2026-09-09** — `Detective/consumption.py` + `tests/test_pinned_decision_consumption_intent.py`. 155 declared decisions swept; every one is consumed or carries a written reason. Two registries, `BY_DESIGN` and `OPEN`, so a real gap cannot read as a design decision, and both rot-checks (stale entry, ghost entry) are pinned. Verified to FIRE by planting an orphan. |
| **The §8.1 digest escalation** | **WIRED 2026-09-09** — it was not, for a full wave, while this file and `INVOCATION_LEDGER.md` both read as delivered. `state_basis` had zero production callers. Now paid at write time (`cli._escalate_suite_digest`) and read through `ledger.suite_state_comparison` ✓ 7/7 + `doctor.same_recorded_state` ✓ 42/45. See `INVOCATION_LEDGER.md` §8.1a, which also states the one-invocation lag. |
| **S3** | RESOLVED with R2; the row said "open" for a wave after it landed. |
| **S4** | **STRUCK — the premise was false.** `refusal` is the `incomplete`-disambiguator, not a "why ungateable" field. Filed by reading the field's NAME instead of its contract. |
| **S5** | Diagnosed by S13, remedy ruled by S15. Closed. |
| **S9** | Struck as calibration, explicitly not a correctness finding. |
| **S10** | RESOLVED — the CLAIM was wrong, not the cache. See D2 for what the repair exposed. |
| **S14** | RESOLVED — two defects: disclosure, and an ordering that inverted Wesker's own phase precedence. |
| **S15** | RULED 2026-09-08: stay on hard pins, no `DetectiveUUT` migration. |
| **§MI** | RESOLVED — an invalid measurement is a RECORD, not an absence, and not a converge target. |
| **#60 MCP drift** | RESOLVED — the MCP surface said COMPLETE where the CLI and the certificate said UNGATEABLE. |

---

## 5. The pattern worth carrying forward

Six defects found on 2026-09-08/09 turned out to be **the same shape**, and it is worth naming
because it is not a coding error — it is an epistemic one:

> **A claim that holds over the subspace where it was checked, with nothing recording that the
> subspace was a subspace.**

- **§MI** — `behavior_status` admitted three of five standings; the other two fell through to codes
  meaning "absence".
- **#60** — the anti-drift test called `certificate_standing` with five of six arguments, so it
  compared two surfaces over exactly the subspace where they cannot disagree.
- **S10** — the cache test's immunity claim held only when the cache was actually used, which it
  often is not.
- **The doctor fence guard** — banned the word "mutant", which a legitimate quoted sentence
  contains; passed only because the branch was unreachable.
- **The signpost** — a branch referencing an undefined name degraded to SILENCE inside its own
  catch-all, so it never fired for two of three fault kinds. Found by three linters, not by 14
  passing tests.
- **"Writes nothing"** — asserted by whole-tree mtime, a proxy that agreed with the intent only
  while the invocation ledger did not exist.
- **The §8.1 escalation** (found 2026-09-09) — the subspace was the DECISION. `state_basis` was
  ✓ COMPLETE, exported, documented and tested, and had no production caller, so every check that
  could pass did, and none of them covered whether the escalation happens. The status vocabulary is
  what carried it: "Built: … `state_basis` …" is true of a decision and silent about a behaviour,
  which is *"two conditions that mean different things must not collapse into one truthy check"*
  applied to prose instead of to code.

**A seventh instance, and it is worth separating from the six.** The six above were all found by
grounding a claim someone had already written down. The seventh was found by asking a question
**nobody had posed** — *is every pinned pure decision consumed in production?* No index can list an
item nobody thought to file, so the closure discipline needs questions of that shape, not just
better indexing.

**That question is now a standing guard** (2026-09-09): `Detective/consumption.py` +
`tests/test_pinned_decision_consumption_intent.py`. 155 declared decisions, each either consumed or
carrying a written reason naming what consumes it. Founder ruling: *"the solution isn't to hide from
the dark, it's to throw some light on it"* — so the registry takes a REASON rather than a bare name,
an empty reason is not an exemption, and `BY_DESIGN` and `OPEN` are separate lists so a defect can
never sit among the design decisions and read as one. `len(OPEN)` is 2 and is meant to go down.

Building it corrected the sweep that motivated it, twice over. The first pass used
`"pure" in docstring`, which matches **"impure"** — and the house convention for extracting a
decision says *place it beside the impure function it serves*. That admitted 7 false positives,
including one carried in the hand-written finding list. The real population is 155, not 157, and the
real count was 9 unconsumed, not 10. The corrected predicate was found by probing its own residual —
§R5b's rule applied to the instrument built to enforce a different rule.

**The two questions still worth asking**, both decidable properties of the reference graph rather
than proxies for meaning: *does every consumer distinguish ALL of a decision's states?* (the
generalised form of §MI and #60) and *does each layer consume the computed signal or re-derive it?*
(which is what W4 was). Neither is built.

The common remedy is not more tests; it is **asking what the check does NOT cover, and recording
that**. A guard that swallows its own failure needs a test per BRANCH, because its failure mode is
indistinguishable from its healthy one.

And the founder's framing, which is the through-line: *"the problem isn't breaking things, it's
breaking things silently — without checking, allowing things to drift endlessly and propagate."*
Every item above is a silent failure. None of them broke a build.
