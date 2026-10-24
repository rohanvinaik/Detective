# Design: declared construction and evidence contracts

## Status and authority

Proposal requested 2026-10-24. The design below is an inference offered for owner
review, not a change to the project's theory or current behavior. Names describe
logical records; they do not reserve Python symbols, CLI verbs or a final wire schema.

The existing oracles remain:

- [COMMUNICATING_DETERMINISM](../../../docs/theory/COMMUNICATING_DETERMINISM.md),
  especially §§3–5, 9 and 11: distinct remedies, absence/unknown, real consumption,
  one derivation with multiple renderers, and the limits of semantic review.
- [The knowability paper](../../../docs/theory/operator_completeness/submission/knowability_ieee.tex):
  retain the stated operator, domain, oracle and purity/totality premises. A finite
  output basis does not decide arbitrary input reachability or intended correctness.
- [ARCHITECTURE §11](../../../ARCHITECTURE.md#11-working-on-this-codebase-the-discipline):
  the proof unit is one function's operators and its tests. Independent intent tests
  remain necessary; characterization can pin an existing error.
- [Cleanup contract](../../../docs/TEST_SUITE_CLEANUP_CONTRACT.md): declarations and
  overlap counts do not authorize deletion or replace affected-obligation proof.

## The useful information flow

Authored intent → admissible construction → qualified observation → decision →
conditional action. Each arrow has a producer, a consumer, an identity/context
basis and a named refusal when a premise is missing.

A declaration narrows what a constructor may propose. An observation resolves only
distinctions its method can establish. A decision uses those facts and retains the
residual. This is the proposed engineering interpretation of compute following
information; no entropy estimate, optimality theorem or speedup was measured.

For every requested computation, record the unanswered obligation, admissible
inputs, expected observation class and downstream decision that can use it. A
consumer cannot promote routing/static evidence into proof. Reuse is allowed only
under the existing freshness/context rules. Work that answers no pending decision
is diagnostic/advisory and must be labelled as such, rather than repeated blindly.

## Responsibilities

| Owner | Proposed responsibility | Authority retained elsewhere |
| --- | --- | --- |
| Contract author | Intent, named obligations/prohibitions, permitted edits and required observations | Cannot declare an observation fresh or a mutant equivalent by schema alone |
| Wesker | Policy-bound catalog, generators, applicability and qualified execution facts | Does not infer intent or control an outer coding agent |
| Detective | Contract admission, existing measurement orchestration, scoped standing, residual and conditional next action | Cannot silently weaken intent to fit available operators |
| Outer controller | Submit candidates, consume allowed actions, supply requested authorized input or abstain | Cannot turn a setup result into completion or acquire authority through a command string |

Only a recorded, scoped grant supplies a human/model judgment. Preserve its origin,
scope and invalidation basis separately from measured facts and proved equivalence.

## Proposed records

### 1. Function contract

One target identity, schema/version, author/intent reference and content digest;
literal-expressible decision inputs where applicable; declared domain/codomain;
named positive and negative obligations; external dependencies; named outcomes and
remedies; required observation kinds; permitted writable cells/paths; immutable
obligation cells; import bindings, location and lifetime; consumers and exemptions.

Separate definition ownership from call relationships. Shared helpers have one
definition owner and may have many callers. Validate dependency/reference edges
without duplicating helpers to force a tree. Dynamic or reflective edges unresolved
by static inspection remain explicitly unresolved or have reviewed declarations.

The constructor may fill only granted cells. Whole replies are admitted or refused;
a failed admission preserves the original contract and files. Revisions identify
the exact prior digest and explicit authority to reopen a completed cell.

### 2. Engine catalog

Versioned export from Wesker's authoritative implementation and policy, with:
operator identity/family, declared obligation reference, implementation/support
state, applicability premises, observation requirements, generator identity and
unavailability reason. Keep theory-declared entries even when implementation is
missing. Runtime applicability is a qualified result, not inferred from a name.

Do not add a second hand-maintained category/visitor table. Reuse B04/B06's
authoritative definitions once accepted. Reflection can describe implementation
shape; it cannot establish semantic coverage or substitute for actual execution.
An advisory catalog read does not create mutants or enlarge a certified universe.

### 3. Observation and decision binding

Bind the applicable source/target, test identities and origin, intent/contract
digest, operator policy/universe, domain/codomain premises, regime, interpreter,
producer/schema versions, invocation and execution context. Retain the current
freshness/containment/validity rules; this envelope does not replace them.

Presence is typed: absent, explicitly unknown, observed empty, observed value,
unsupported and invalid do not share a default. Multiple blockers remain together.
Keep these judgments separate:

1. Structural admission under the supported construction language.
2. Load/collection validity in the actual regime.
3. Admissibility of the observation, including containment and budgets.
4. Specification standing relative to the declared operator/oracle/domain basis.
5. Authored intent acceptance, including any residual or scoped grant.
6. Authorization to edit, delete, place or publish.

No single complete flag or quality score stands in for this tuple. Code that
compiles can still be unmeasurable, under-specified, wrong for its intent or
unauthorized to write. A supported output alphabet does not establish the selector
mapping from inputs to outputs.

### 4. Consumer and action contract

For every decision code and computed field, declare actual production consumers or
an exemption with a reason naming its alternate consumer. Each consumer handles all
applicable states, including reviewed, explicitly justified collapses. Account for
serialization by reflection, dynamic attributes and public external consumers;
absence from a static reference graph alone cannot prove deadness.

An action carries a named code, target/scope, required premises, evidence basis and
bounded argv when a command is warranted. Execute without a shell. Revalidate the
applicable basis at execution. Missing/changed premises yield a named hand-back;
they never authorize a guessed rerun, automatic flag or wider edit.

Use the existing single decision derivation for terminal output, full report, JSON,
ledger and certificate projections. Each surface preserves the distinctions it
claims to communicate; purpose-specific projections/omissions must be declared.
Natural-language fidelity still needs semantic review, not a schema-pass claim.

## Construction boundary

The initial supported scope should be narrow: a pure decision over literal inputs,
its declared codes, explicit consumer adapters and new-file source/test scaffolds.
Generate structural material mechanically from an approved declaration. Authored
intent expectations must not be inferred from the candidate's result, and generated
expected behavior must not be its own only oracle. Reuse current witness writers.

No blanket import hoisting. Module-level, local/lazy, optional-dependency and
TYPE_CHECKING imports have different timing and failure behavior. A contract names
the permitted binding/location/lifetime; unsupported constraints refuse admission.
AST rendering is suitable for a newly declared file within a supported dialect.
Rewriting existing files requires a separately accepted preservation/edit primitive;
AST unparse does not preserve comments, formatting or every execution distinction.

Schema-constrained output bounds admitted structure, not execution effects, native
liveness or resource allocation. B01 containment, B02 filesystem authority and B08
edit/recovery guarantees continue to apply at real execution/write boundaries.

## Apply the discipline to repairs without expanding them

| Existing work | Immediate method | Additional capability proposed here |
| --- | --- | --- |
| B04/B05 | Write cause/count/decision obligations and trace all existing consumers | Optional imported contract and machine-checked consumer interchange |
| B04/B06 | Establish the already-promised operator definitions and consumption | Stable public catalog export for external construction tools |
| B08/B11 | Record test obligations, origin and retained witnesses | Optional contract provenance; no new deletion algorithm |
| B00/B12 | Bind actual source, lock, CI and artifact evidence | Reuse these facts; do not rebuild the existing exact-CI release guard |

The first column remains repair work. Neither schema implementation nor external
construction support is a prerequisite to finishing those repairs or publishing a
correct paired update. Current CLI users remain supported without a contract file.

## Pilot, evidence and resource accounting

After owner review, select one small existing B05 decision/consumer boundary. Record
its current obligations and independent intent expectations before generation.
Compare accepted/refused outcomes through the real CLI and all emitted artifacts:
known cause, several simultaneous causes, absent evidence, explicit unknown, empty
observation, malformed input, stale identity and an unsupported observation.

A deliberate new code or field with no consumer must be detected or explicitly
unresolved; a declared but bypassed consumer cannot satisfy acceptance. Mutation
tests guard the pure decision; adversarial intent tests guard meaning and boundaries.
Keep existing rare refusal witnesses and the nine status characterization cases.

Only then consider extending the supported construction language. Measure production
work, elapsed time, CPU, allocations/RSS and evidence-equivalent outcomes before
claiming savings. Attribute any removed work to an unchanged required answer;
neither fewer tests nor fewer branches is a performance result by itself.

## Open owner decisions before implementation

- Initial construction dialect and interpreter compatibility policy.
- Whether the first public surface admits completed contracts only or also emits
  new-file scaffolds; command/API names and compatibility/migration policy.
- Exact treatment of shared helpers, optional/lazy imports and reflective consumers.
- Which obligation language is decidable by the initial validator, and which asks
  remain authored intent or an explicit unsupported residual.

No proposed code chooses these silently. Unsupported scope is retained and handed
back. #90's effect-world contracts, #135's negative proof rules, autonomous model
services and bulk cleanup remain separate proposals.
