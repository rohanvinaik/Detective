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
