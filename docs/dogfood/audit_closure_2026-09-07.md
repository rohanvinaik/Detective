# Audit closure — 2026-09-07

Status: implementation and theory repairs complete within the reviewed scope; final paired
suite gates PASS. This is not a universal correctness or equivalence certificate. No GitHub
issues have been closed, no package published, and no commits or pushes made in this repair wave.
The operational handoff is [CLOSURE_HANDOFF.md](CLOSURE_HANDOFF.md).

The original audit covered `863d295..fccee9c`, the working-tree reproducibility gate, and the
uncommitted theory drafts. Existing user edits were retained. The recorded issue #68 opaque
representation boundary remains a deliberate fixture hand-back, not an arbitrary object factory.

## Audit and ledger reconciliation

| Audit / ledger | Repair and evidence | Standing |
|---|---|---|
| 1–2 / B | Fresh isolated verification bypasses cache, checks validity and basis, compares scored mutant and survivor IDs, and absorbs exceptions/cuts. Classifiers reuse the exact supplied profile. | Implemented; adversarial CLI tests and pins |
| B downstream | Audit's flat completeness fields and rewrite preservation consume validity. Neighbor measurements cannot authorize removals when invalid. | Implemented; direct consumer regressions |
| B backend | Worker compilation uses pytest's package identity; module/local/indirect calls install and restore mutations; execution selectors map back to baseline IDs. Value-kill attribution follows the actual asserting test and stops before later tests can erase it by timeout. | Implemented; package/namespace, indirect-call, crash-first and blocking-tail tests |
| B accounting | Construction, installation and entry failures cannot produce a vacuous certificate. They are disclosed separately from trace truncation. Candidate removal spellings are normalized before obligation comparison. | Implemented; zero-universe and cross-file bridge regressions |
| 3 / D | Exact qualified or unique bare target selection; missing/ambiguous targets refuse. | Implemented; duplicate-method and missing-target tests |
| 4 / D | Extraction keeps scalar parameters and prefix projections the residual reads; unknown dependencies, imports, nested scopes and read-before-write inputs remain unresolved. | Implemented; scalar `k`, argparse and overwrite regressions |
| 5 / D | Arbitrary calls, slices and element reads no longer become assumed primitive inputs. Only bounded recognized conversions support proposals. | Implemented; four unknown-projection counterexamples |
| 6 / D | Tuple indexing alone no longer implies ndarray; dictionaries supply a counterexample. | Implemented; intent test and conditional pin |
| 7 / D | Outer tensor annotations are not counted as heavy library body use. | Implemented; annotation-only regression |
| 8 / E | Diagnostic module execution registers its module while dataclasses inspect it, then restores the prior registration. The real dependency error is retained. | Implemented; postponed-dataclass/missing-dependency test |
| 9–11 / D | Survey honors project root, discloses unreadable/unparsed files, and states the bounds of an empty scan. Missing extraction targets are precondition errors. | Implemented; actual CLI tests |
| E/F guidance | CLI/MCP preserve the same refusal cause and route object/line gaps to fixtures. Unknown harness failures do not prescribe more budget. | Implemented; paired surface tests and route pins |
| 12 / theory | Surviving guard means unobserved output, not proven reachability; finite Boolean output does not decide reachability. | Prose corrected; concrete Lean counterexample |
| 13 / theory | Independent sampling succeeds almost surely iff the killing region has positive sampling probability; conditional coupling does not force probability zero. | Corrected support theorem and Boolean counterexample |
| 14 / theory | Sufficiency requires pointwise footprint coverage, not one subsuming operator. | Corrected prose; Lean counterexample |
| 15 / theory | Constant-oracle vacuity and nonconstant-oracle hypotheses are explicit; set-theoretic relativization is separated from effective decidability. | Corrected prose; empty-footprint Lean counterexample |
| 16 / theory | Intent mutual information requires a joint experiment over latent intent and test selection. Syntactic edges do not prove statistical dependence or a composition gap. | Corrected model and counterexamples |
| Additional theory defect | Singleton-regime undecidability reduction had reversed a containment condition. It now uses the full footprint criterion. | Prose corrected; reduction not claimed mechanized |
| Ledger Step 3 | Small numeric NumPy arrays require a real type binding, preserve shape/dtype, and get independent trial copies. Literal grammar is unchanged. Unknown objects retain the fixture route. | Implemented; actual array CLI + generated pytest, 42/42 decision pin |
| Exception-message lead | Reconstructed the shared guard with duplicate tests and exact raises-message assertion; two isolated convergence passes and resulting pytest pass. | Bounded reproduction passes; absent external checkout not rerun, historical root cause unclaimed |

Ledger A and C were already repaired at the start of this closure; their recorded historical
revalidations remain historical evidence. The withdrawn Step 2a proposal stays withdrawn. This
repair does not replace undecidable equivalence/reachability with input guessing or a flag.

## Symbolic trace

Serena traced profile → classification → convergence/audit → normalized validity → FunctionBasis,
certificate standing and rewrite verification. Verification uses the same source/test identity,
extra-test scope and scored obligations as the profile it confirms. Required failures are absorbing.

The backend trace reaches `_evaluate_isolated` → worker collection/module compilation → test and
module binding patches → entry observation → reason attribution → result identity → kill/line
obligations → audit and removal decisions. The full-suite regressions demonstrated why selector
spelling and actual killing-test identity must survive every boundary. The default-argument pin
exposed the separate timeout-after-assertion defect; increasing a timeout would have hidden its cause.

Extraction resolves the requested AST symbol before survey matching, computes a bounded interface,
and carries unresolved dependencies through both JSON and human renderers. These are proposals,
not proofs of purity, reachability or behavior-preserving extraction.

## Detective pin receipts

These are observed operator-universe receipts, with green generated/intent test verification.
Run-kill counts are quoted as emitted; conditional residuals remain explicit.

| Decision | Receipt |
|---|---|
| verification_disposition | COMPLETE, 19/19 |
| should_verify_reproducibility | COMPLETE, 6/6 |
| measurement_cut_reasons | COMPLETE, 35/35 |
| residual_input_route | COMPLETE, 7/7 |
| rewrite_classification_status | COMPLETE, 10/10 |
| extraction_target_status | COMPLETE, 16/16 |
| extract_readiness | COMPLETE, 18/18 |
| survey_scan_status | COMPLETE, 7/7 |
| array_source_disposition | COMPLETE, 42/42 |
| isolated_test_selection (Wesker) | COMPLETE, 15/15 |
| repair_measurement_route | COMPLETE modulo 2 unproven equivalents, 48/48 run-kills |
| usage_inferred_type | COMPLETE modulo 1 crash-only value gap, 7/7 run-kills |

No equivalence flags were invented to discharge these residuals. A conditional receipt does not
assert arbitrary-program equivalence or the correctness of a normative specification.

## Formal artifact verification

- Lean 4.28 / pinned Mathlib checks all 29 theorem declarations in adequacy_completeness.lean.
- Every declaration's axiom footprint was inspected: no sorryAx; at most propext,
  Classical.choice and Quot.sound. One pre-existing unused-variable warning remains.
- The added counterexamples are surviving_guard_without_gap, one_subfootprint_is_insufficient,
  and empty_footprints_score_without_observations.
- Computability reductions and the companion probability model are prose arguments, not Lean proofs.
- Knowability's IEEE artifact rebuilt successfully to a nine-page PDF; extracted text includes
  the corrected pointwise, oracle and undecidability qualifications. The older LNCS paper is
  preserved as a historical companion artifact, not mislabeled as the new draft.
- All 12 reference hashes now match after reviewing the exact historical changes. Six external
  citations remain explicitly unverified. See reference_reconciliation_2026-09-07.md.

## Final gates

- Detective: both full runs exited successfully; the counted run reports **2663 passed,
  24 skipped, 2 warnings** in 206.88 seconds. Both warnings concern the existing TestRegime
  dataclass being considered for pytest collection.
- Wesker: both full runs pass **705 tests** (33.40 and 32.97 seconds).
- Pinned Ruff 0.14.10: Detective (344 files) and Wesker (140 files) format/check gates pass.
  Wesker check and format-check were repeated after the final test expectation correction.
- `git diff --check` passes in both repositories.
- The final Wesker correction asserts that a construction failure refuses the gate while
  retaining `coverage_depth="profiled"`; its separate harness failure reason must not be
  conflated with trace truncation. No behavior was weakened to satisfy the test.

Durable suite, pin, reference and Lean logs are in
[closure_evidence_2026-09-07](closure_evidence_2026-09-07/). Intermediate failed pin logs are
historical diagnostics; the receipt table above identifies the final successful outcomes.
No new source edits are required by these final gates. Work remains uncommitted alongside
pre-existing user edits; no publish, push or issue closure has occurred.

The latest usage check after the window reset was **1% five-hour / 32% weekly**, with zero
reset credits. These are shared account windows, not this task's exact token or cost total.
The assistant did not redeem a reset credit. The preceding window reached 97% before this
checkpoint; future continuation should update the handoff before approaching that limit.
