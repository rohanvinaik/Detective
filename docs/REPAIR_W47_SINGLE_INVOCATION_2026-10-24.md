# W#47 — a test exception cannot select a second invocation

2026-10-24. Existing-contract repair in B03, with observation identity carried through
B04. [Wesker#47](https://github.com/rohanvinaik/Wesker/issues/47) tracks this bounded
defect; it does not accept either repair package as a whole.

Wesker implementation: [ca215e4227268726513817d63be7a41958b9cc9c](https://github.com/rohanvinaik/Wesker/commit/ca215e4227268726513817d63be7a41958b9cc9c).
Detective's development lock selects that exact SHA and `uv sync --locked`
installed it. The bounded repair and consumer checks below are accepted on this
basis; the rest of B03/B04 remains open.

## Defect and resulting behavior

The unpatched path in `Wesker.engine._run_test_with_timeout` formerly called
`test_fn(mutated_func)` and retried `test_fn()` on any TypeError. The exception
could have come from the entered test or the mutant, allowing duplicated effects
and survival after an execution failure.

Arguments are now selected before invocation, inside the same bounded worker:

- A patched test receives no injected argument.
- An inspectable unpatched callable prefers the injected form. Only a successful
  zero-argument binding can select the empty fallback.
- Inspection uses the callable's actual signature, without following `__wrapped__`;
  fixture-bound wrappers keep their own invocation convention.
- An unavailable signature retains one injected attempt. Execution exceptions
  reach the existing classification; they never authorize another call.

A TypeError remains a crash outcome, not value pinning. `evaluate_mutant` retains
its intentional separate original-control observation for attribution. That
control is not a fallback retry and is explicitly distinguished by the regressions.
Normal/converged in-process paths share this runner. The isolated path delegates
invocation to pytest and has no duplicate copy of this retry handler.

## Evidence identity

The operator universe counter remains 8. Category definitions and fingerprint
counts were compared before/after and are identical for both signs. The declared
observation rule changes the content hash:

| Basis | Before | Corrected |
| --- | --- | --- |
| One-sign | `8.dcc355186875` | `8.68a525594c46` |
| Two-sign | `8+neg.671d835828bf` | `8+neg.40ae45e28e39` |

Detective's existing policy adapter carries the new identity into its engine
fingerprint and verdict key. Identical target/tests/budgets therefore do not reuse
the older result under the corrected observation basis. No human input, judgment
or generated certificate was purged or relabelled. Package versions and published
1.2.2 artifacts remain unchanged; this is a development-source update.

## Verification

- New live-boundary intent suite: 14 cases. The unfixed baseline produced six
  failures/eight passes; the corrected runner passes all 14. Obligations cover
  body/mutant exceptions, actual evaluation in both killer-recording modes, empty
  invocation, bound/partial/callable objects, unavailable signatures and wrappers.
- Final Wesker suite: **1,093 passed**, including real CLI normal/isolated acceptance.
- Installed-dependency checks: **29 passed** with local Wesker shadowing disabled,
  covering the new regressions and existing policy/cache consumer tests.
- Final full Detective suite against the local pair: **3,872 passed, three skipped,
  one expected failure** in 144.45 seconds.
- Pinned Ruff 0.16.7 check and whole-tree format checks passed in both repositories.
- Advisory ty reported two deprecations in unchanged context-manager declarations.
  Pylint was run against both the baseline archive and current source; it is not
  globally clean. Line-offset/module-size and cycle-report differences were retained
  in the comparison receipt. No clean pylint/local-Sonar or blanket quality claim is made.

Exact Wesker [CI 40124600315](https://github.com/rohanvinaik/Wesker/actions/runs/40124600315)
completed successfully on the implementation SHA above; its CodeQL run also
completed successfully. The separate full-specification workflow is not accepted
by this receipt. Detective's next exact-commit CI is a distinct observation after
the consumer push, not inferred from the local suite.

The installed distribution's VCS metadata names the exact Wesker SHA above. Its
`engine.py` SHA256 is
`4b9b4fb1037ad8ec04c2998b61e06ad7bf159f5f2ccf149dc20b773f4464976e`,
matching the local source bytes. The boundary accepts live callables; these are
hand-written intent tests, not a fabricated literal-input mutation pin.

Local raw receipts are under
`~/Library/Logs/Detective/repair-W47-2026-10-24/`: baseline regression output,
`wesker-accepted.log`, `detective-accepted.log`, installed provenance, before/final
policy records and the advisory type/lint reports. Read complete outputs and bind
them to their recorded basis; earlier intermediate runs are not final receipts.
