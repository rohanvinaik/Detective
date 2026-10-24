# B02 execution record — 2026-10-24

This is an incremental repair receipt, not acceptance of the whole package.
The shared scope remains `REPAIR_HANDOFF_2026-10-24.md`.

## Basis and protected obligations

Starting source: Detective `639a0c7`, Wesker `8b6f222`. Detective's development
lock selects that Wesker revision. Managed CPython 3.14.7 resolves both local
repositories under the prescribed pair PYTHONPATH.

The initial Detective tree already had one certificate-ledger addition for
`Detective/cli.py::_final_banner_status`, with standing `incomplete`. It was
preserved separately and is not part of this repair's proof or commit.

Protected obligations: a harvested row describes call-entry arguments; aliases
within that row survive; different rows and later trials cannot mutate its entry
state. Missing snapshot evidence must reach the public refusal path, rather than
look like an empty input pool or an exception in the target.

## Entry snapshots — implemented

`capture_call_inputs` deep-copies the complete positional tuple in its PY_START
observer, before execution of the target body. Copying the complete tuple retains
its internal aliases. Copy and representation failures are recorded by the observer
and raised as `ObservationIncomplete` after worker retirement and cleanup:
`input_snapshot_failed` or `input_snapshot_unrepresentable`.

The five authored boundary tests failed before the repair. Afterward:

- Focused capture suites: 62 passed.
- Full Detective suite against local Wesker: 3,849 passed, four skipped, one xfailed.
- Full Wesker suite: 1,076 passed.
- Ruff 0.16.7 check passed; whole-tree format check passed, 469 files.
- Advisory ty reported seven warnings outside the changed files; it exited 1.

Full suite logs and the disposable CLI fixture are retained locally under
`/tmp/Detective-B02-entry.5EQojh/`. The snapshot instrumentation takes live
callables, so authored boundary tests are the applicable verification route.
No generated certificate or speedup is claimed for this shell.

The CLI walk used a fresh project, `--help`, a clean `regime`, then:

```text
detective converge subject.py::read --deadline 30
```

Its target required an object whose deepcopy raises TypeError. The public command
returned exit 3 and named the observation failure:

```text
INCOMPLETE:  input_snapshot_failed: entry arguments could not be retained independently (TypeError)
```

## Published minimum — reproduced, unresolved

In an isolated environment containing published Wesker 1.1.1, pytest and Ruff,
with only repository Detective on PYTHONPATH, `import Detective` fails through
certify → engine → capture:

```text
ImportError: cannot import name 'JoinedWorker' from 'Wesker.interrupt'
```

This tests current repository source against its declared minimum, not an older
Detective distribution. The Git development pin does not establish compatibility
with the declared published dependency. Neither a new release nor an invented
unpublished version floor was introduced in this pass.

## Remaining B02 work confirmed in current code

- `_outcome` already copies a complete unwrapped argument row per trial, but the
  copy currently happens before its bounded worker starts.
- `_search_witness` still calls `_outcome_value` to re-execute original and mutant
  while constructing a witness. State fallback similarly re-executes through
  `_receiver_state_after`. Carry admissible value/state observations instead.
- `property_holds` still compiles and executes generated code without a worker
  boundary. Witness rendering/writing also needs the aggregate remaining budget.
- The existing speculative write guard explicitly leaves profiled existing tests
  free to write. D#105 remains to be implemented against explicit test/regime write
  authority; permitting the entire system temp directory is not that authority.
- `_outcome` currently renders a filesystem interception as a raised target marker;
  an instrumentation refusal must not become a target distinction.
- `literal_source` already renders nonfinite floats as executable constructor
  expressions. D#76 still needs verification of assertion and printed-mutant
  consumers; do not reimplement the existing literal renderer merely from the list.

Resource outcome is unmeasured. Deepcopy adds necessary observation work; passing
tests and incidental suite durations do not establish a performance improvement.
No issue was closed by this partial repair.
