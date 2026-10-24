# Proposal

## Why

An external tool constructing a function needs a bounded description of what it
may write, which distinctions it must preserve, what evidence is available and
which action that evidence warrants. Reconstructing these from implementation
details and human reports creates competing authorities and loses distinctions.

The proposed enhancement makes that boundary explicit. Authored intent constrains
construction; Wesker owns the operator/observation facts; Detective owns their
qualified specification standing and next action. Structural admission supplies
no behavioral certificate by itself.

## What Changes

- Propose a versioned, engine-owned catalog exposing actual operator support,
  applicability premises and observation requirements under a named policy.
- Propose an optional function-level contract accepted by Detective: authored
  obligations, permitted construction, import/binding constraints, evidence basis,
  named decision states and their real consumers.
- Validate contracts before execution or writing; return distinct named refusals
  for unsupported grammar, invalid structure, missing authority and stale basis.
- Initially render only reviewable new-file scaffolds and adapters from approved
  declarations. Reuse current measurement/witness machinery; keep independent
  intent tests and preserve all existing safety/authorization boundaries.
- Make the evidence needed for each next action explicit, allowing an outer
  controller to consume Detective's decision without inventing intent or a verdict.

## Capabilities

### New Capabilities

- `construction-contracts`: optional versioned declaration/admission, authoritative
  catalog interchange and evidence-qualified construction hand-offs.

### Modified Capabilities

None approved. B00–B12 repair current promises independently. Any public schema,
CLI/API naming and supported dialect require owner review before implementation.

## Impact

Wesker would own the catalog export; Detective would own admission, obligation and
decision-consumption adapters. Dependency direction remains outer controller →
Detective → Wesker. Neither package imports an external construction system.

This is deferred Type (2), separate from effect contracts (#90), certified negative
residuals (#135), sweep editing (#136), and existing B04–B06 correctness repairs.
It creates no new equivalence proof, semantic oracle, deletion authority, release
requirement, model service or performance claim.
