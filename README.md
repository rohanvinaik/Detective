# Detective

Behavioral-scope diagnosis, complete-test-suite synthesis, and **provably
behavior-preserving decomposition** for a single Python function — built on the
[Wesker](https://github.com/rohanvinaik/Wesker) mutation engine.

Point Detective at `file.py::function` and its mutation profile tells you exactly
what the function does *and* where its behavior is left unspecified. From that one
map it generates a **mutation-complete, minimal pytest suite** for free, and — when
you ask — extracts entangled blocks into cleaner helpers, applying the change only
when the generated suite proves behavior is preserved.

Clean-room package on **Wesker + stdlib only** (no LintGate in the runtime graph).

## Thesis

A function's mutation profile is a complete map of the behavioral distinctions it
makes: a killed mutant is a distinction the tests pin, a survivor is a degree of
freedom no test distinguishes. Read backwards, that map is a *specification*. Two
things fall out of it:

- **The suite is free.** If you know every behavioral degree of freedom, you know
  exactly which tests the function needs — Detective writes them (minimal, kills
  every killable mutant, retains and documents the equivalents).
- **Decomposition is provable.** A mutation-complete suite *is* the behavioral
  contract, so a refactor that keeps it green provably preserves behavior. That is
  the guarantee behind `decompose --apply`.

*Value-specification:* only an assertion kill (which pins the return value) counts
as specified; a crash/timeout kill proves the code runs, not what it computes.

## Install

```
# from GitHub — pulls the Wesker engine automatically:
pip install git+https://github.com/rohanvinaik/Detective.git

# local dev (Wesker resolved from ../Wesker, editable):
uv sync
```

## Usage

```
detective diagnose  file.py::fn           # read-only: behavioral scope + what to run next
detective converge  file.py::fn           # flagship: write a complete, minimal pytest suite
detective decompose file.py::fn --apply   # extract helpers, applied only when proven safe
detective audit     file.py::fn           # assess an existing suite: complete? minimal? prune?
detective flag      file.py::fn ID        # mark a survivor equivalent (manual oracle)
detective purge                           # delete regeneratable analysis cruft
```

Useful flags:

- **Parallelism** (`diagnose`/`converge`/`audit`): default is **adaptive auto** — a
  tiny probe measures the function's per-mutant cost and fans out across CPU cores
  only when it pays off (memory-bounded by construction, verdicts identical to
  serial). `--parallel` forces it; `--serial` disables it.
- `converge --fast` — greedy-sample a `(1−1/e)`-optimal subset per pass (vs the
  default full universe). `converge --input "(…)"` / `decompose --input "(…)"` —
  supply a residual input the tool asks for when synthesis can't build a valid one.
- `diagnose --learn` — surface which mutation categories this project recurrently
  leaves value-unspecified. `audit --remove` — confirm deletion of pointless tests.

Generated tests land in `tests/test_<fn>_synth.py` with a wired `conftest.py`; run
them with `pytest` (only the generated ones: `pytest -m detective`).

## Dependencies

One runtime dependency — `Wesker` — plus the standard library. No LintGate runtime
dependency. Requires Python ≥ 3.11.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full module layout, the complete
per-command CLI reference, the performance/memory layers, and the debug map.

## License

MIT © 2026 Rohan Vinaik
