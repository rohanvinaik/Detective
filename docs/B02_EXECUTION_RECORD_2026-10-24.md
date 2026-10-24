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

## Published minimum — reproduced; repaired for the paired 1.2.0 update

In an isolated environment containing published Wesker 1.1.1, pytest and Ruff,
with only repository Detective on PYTHONPATH, `import Detective` fails through
certify → engine → capture:

```text
ImportError: cannot import name 'JoinedWorker' from 'Wesker.interrupt'
```

This tests current repository source against its declared minimum, not an older
Detective distribution. The Git development pin does not establish compatibility
with the declared published dependency. Neither a new release nor an invented
unpublished version floor was introduced during that first pass. The owner then
selected 1.2.0 for both packages. Detective now requires Wesker 1.2.0 and its lock
selects the pushed Wesker 1.2.0 commit. Installed-artifact acceptance belongs to the
paired release receipt; Wesker must reach PyPI before Detective.

## Same-invocation witness observations — implemented

Witness search now retains entry arguments, the return payload and optional receiver
state from the bounded invocation that produced its outcome marker. Original and
mutant payloads are copied before another arm can alter shared objects. The worker
also owns trial-input copying, so user copy hooks run inside its timeout boundary.
An uncopyable result raises the named `outcome_snapshot_failed` observation refusal;
an interrupted copy publishes no partial payload. Consumed iterators retain their
existing bounded observation rather than being executed again to reconstruct values.

The unbounded `_outcome_value` and `_receiver_state_after` paths were removed after
checking their consumers. State-witness pins consume the retained receiver states,
and each state-fallback arm receives the remaining deadline independently.

Seven authored boundary tests protect call counts, marker/payload consistency,
mutable-return retention, valid None returns, receiver state, worker-owned copying,
and failed/interrupted snapshots. Verification:

- Focused equivalence/capture/divergence suites: 70 passed.
- Full Detective suite against local Wesker: 3,856 passed, four skipped, one xfailed.
- The final change to consume markers from the retained carrier was followed by a
  fresh focused run: 70 passed. The full-suite receipt precedes that final change.
- Ruff 0.16.7 check and whole-tree format check passed, 470 files.
- Advisory ty still reported the same seven warnings outside the changed files.

The full log is retained in the same local receipt directory as
`Detective-observation-suite.log`. A separate disposable project followed `--help`,
clean `regime`, and `converge subject.py::select --deadline 30`. Its set-valued
target reached `COMPLETE (operator universe)`, 8/8 killed, with fresh isolated
reproducibility confirmation. This is a real-entry-point integration smoke, not
proof that initial synthesis exercised the changed witness-search branch.

Thread interruption bounds the tested Python copy loop; it is not a hard RSS bound
or a guarantee of interrupting native code that holds the interpreter lock.

## Remaining B02 work confirmed in current code

- `property_holds`, property/witness construction, golden capture and suite rendering
  now run in bounded workers. Converge threads the remaining aggregate deadline into
  those phases and checks it before subsequent witness rows. Timeout, unavailable
  observation and uncontained execution remain distinct from a false assertion.
- The speculative write guard now reports `filesystem_write_blocked`, including
  writes whose control exception was caught by a target or iterator. Copy hooks are
  guarded too. Worker-based harvest propagates monitoring/observation refusals.
  Tool-owned bytecode-cache maintenance and Ruff pipes stay outside target write
  guards; legitimate imports suppress bytecode output during property verification.
- The existing speculative write guard explicitly leaves profiled existing tests
  free to write. D#105 remains to be implemented against explicit test/regime write
  authority; permitting the entire system temp directory is not that authority.
- `literal_source` already renders nonfinite floats as executable constructor
  expressions. D#76 still needs verification of assertion and printed-mutant
  consumers; do not reimplement the existing literal renderer merely from the list.

Resource outcome is unmeasured. Deepcopy adds necessary observation work; passing
tests and incidental suite durations do not establish a performance improvement.
No issue was closed by this partial repair.
