# §9.5 experiment: uniform output operators on four Python libraries

This folder reproduces every number in §9.5 of `../KNOWABILITY.md`.

```bash
python run.py        # ~10 minutes with 8 workers; clones and builds under ~/.cache/knowability-experiment
python analyze.py    # prints the tables and writes results/summary.json
```

Requirements: Python 3.10+ to drive the scripts, `uv` (it builds a CPython 3.12 venv per library), `git` and
network access. `run.py --work DIR` relocates the working directory; `--workers N` sets parallelism.

## What it measures

The model's operator is the uniform post-composition `p ∘ f`: run the function, then perturb its returned
value. `transform.py` inserts `@__omut__("module:Qual.name")` as the innermost decorator of every candidate
function in a copy of the library; `omut.py` implements it. Only the outermost call is perturbed, so a
recursive call inside `f` sees the unmutated function. `omut_plugin.py` (a pytest plugin) attributes
recorded values to tests, restricts a run to selected tests, and classifies each failure:

- `assert`: the test's own check rejected the result, meaning an `AssertionError` raised in test code,
  `pytest.fail`, `pytest.raises` not raising, or a doctest output mismatch;
- `crash`: anything else, including an exception or `assert` inside library code, a setup or teardown
  error, or a timeout (20 s per test).

The **value oracle** kills on `assert`; the **any-failure oracle** kills on either.

Per sampled function the mutants are one constant `return c` (a type-appropriate default chosen so that
some observed output differs from it, else `None`) and point swaps `r → c` for every observed `r ≠ c`
(sampled down to 12). Under the paper's model the constant is killed iff some swap is (§9.5); `analyze.py`
checks that per function, treating a swap that was never applied (its value did not recur) as missing.

## Pipeline (`run.py`)

1. **setup**: copy the pinned checkout, inject decorators, build a venv, install the library editable with
   its test dependencies (pinned `pytest==9.0.2`, `pytest-timeout==2.4.0`; the full resolution is saved as
   `results/<lib>/environment.txt`), and install the runtime through a `.pth` file.
2. **baseline**: run the suite twice with the decorator installed and inactive, and once on an undecorated
   copy; a test is usable only if it passed all three times.
3. **record**: run the usable tests, logging each candidate's returned values per test.
4. **sample**: eligible = covered by a usable test, every observed value has a stable `repr` (no memory
   address), and not only `None`; seeded sample (`SEED = 20261106`) of at most 40 per library.
5. **mutate**: run each mutant against the function's covering usable tests, counting how often the
   operator was applied.

## Pins

| Library | Release | Commit |
|---|---|---|
| boltons | 26.2.0 | `4332b35a278d694f30c99881faa61cde695c7a96` |
| inflect | 7.6.0 | `f51d6c43580a717c7a04b71779e61b9979851015` |
| toolz | 1.2.0 | `451af60dec590a6010e2babdbf391ea8f815122f` |
| humanize | 4.16.0 | `3c577d7650508d52aa2982e930b0e744c343082f` |

## Exclusions, recorded in `results/<lib>/`

- `baseline.json`: tests collected, passing runs, and the tests whose outcome differs between the decorated
  and the pristine copy. There are nine, all excluded: four in boltons, which pickle classes made by factories
  that read the caller's frame or inspect frames directly; and five in inflect, which check `typeguard`
  runtime validation, which does not instrument a wrapped function.
- `eligibility.json`: every candidate's eligibility verdict (not covered / unkeyable outputs / returns only
  `None` / eligible), the seed, and the sample size.
- `plan.json`: each sampled function's covering tests, observed value keys and types, its constant, and its
  swaps.

## Raw records

`observations.jsonl.gz` (one line per recorded return: function, test, value key, type) and
`mutants.jsonl.gz` (one line per mutant: function, operator, application counts, and every covering test's
outcome) are what `analyze.py` reads. Values themselves are not stored, only a type name and a hash of their
`repr`.
