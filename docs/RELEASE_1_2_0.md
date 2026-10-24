# Paired 1.2.0 update

This update brings the existing local Wesker/Detective implementation to the
published packages. It preserves the local command and capability surface; it
does not wait for every item in the mechanical repair handoff to be completed.

## Runtime and dependency boundary

Both packages require Python 3.12 or newer. Detective 1.2.0 requires
`Wesker>=1.2.0`. Published Wesker 1.1.1 lacks `JoinedWorker`, which the current
Detective execution paths import. The development Git lock previously concealed
that incompatibility. The wheel dependency is a plain package requirement; the
development Git URL is not a published runtime dependency.

The dependency lock follows Wesker commit
`9fa1824f7634e86632b31ddbc40083a40eb68142`.

## Included working implementation

- Owned monitoring subscriptions, thread attribution, cancellation and qualified
  execution observations from the local Wesker engine.
- Isolated execution and memory-limit CLI wiring already present in Wesker.
- Policy 8 annotation exclusion and the existing mutation/operator implementation.
- Detective's current diagnostics, separate mutation/value accounting, two-sign
  command paths, synthesis, audit and rewrite machinery.
- Independent call-entry argument snapshots and witness payloads retained from the
  same bounded original/mutant invocations that established their distinctions.
- Bounded generated-property checks, golden capture and witness/suite rendering.
  These phases draw from the remaining command deadline. Failed observations and
  intercepted speculative filesystem writes retain named refusal outcomes.

The update does not claim that the whole repair handoff has been accepted. In
particular, containment of filesystem writes made by existing profiled tests,
hard native-code/resource containment and the wider safe-removal work remain
separate engineering obligations. No tests were purged for this update.

## Publication order

Publish Wesker 1.2.0 first, then detective-spec 1.2.0. The existing release workflows
build and attach signed GitHub release artifacts; they do not upload to PyPI.
Use the wheel and sdist from each committed candidate. Installed-package checks
must use both candidate wheels without PYTHONPATH before upload.

## Candidate acceptance — 2026-10-24

Runtime source: Wesker `9fa1824`, Detective `02d96d2`. The remaining record-only
commit changes this document; it does not change the installed package modules.

- Full local pair: Wesker 1,076 passed; Detective 3,861 passed, four skipped and
  one expected failure. Pinned Ruff check and whole-tree format checks passed.
- Wheel and sdist built successfully for both distributions from clean committed
  worktrees. Both sdist tracked-file checks and all four Twine metadata checks passed.
- Every tracked package file matched its wheel member byte-for-byte: 27 Wesker
  files and 59 Detective files, with none missing or different.
- Fresh managed Python 3.12.12 and 3.14.7 environments installed both candidate
  wheels with ordinary runtime dependencies and no PYTHONPATH. Imports and console
  startup resolve the installed 1.2.0 packages. Metadata requires `wesker>=1.2.0`
  without a development Git reference.
- On each interpreter, a fresh shipping-rule project followed help → clean regime
  → converge. Both runs reached `COMPLETE (operator universe)`, 17/17 mutants killed,
  three generated tests, and fresh isolated reproducibility confirmation.
- Installed Wesker also profiled that suite with `--isolated --mem-limit-mb 256`:
  17/17 killed and 12/12 dimensions covered.

Complete local logs, disposable projects and artifact manifests are retained in
the release receipt directory. The pre-existing certificate-ledger worktree edit
was left untouched and was excluded by building from committed worktrees.
