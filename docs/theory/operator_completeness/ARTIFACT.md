# Artifact: *What a Mutation Regime Can Know About a Function*

Three independent parts, each runnable on its own. Which paper claim each part supports is listed in
[`THEOREM_LEDGER.md`](THEOREM_LEDGER.md).

| Part | What it establishes | Needs |
|---|---|---|
| [`proofs/`](proofs/) | the mechanized theorems (38, no `sorry`), with an axiom audit that fails the build on any deviation | `elan` (Lean toolchain manager), network for the Mathlib cache |
| [`checker/`](checker/) | Theorem 3.2 as a decision procedure that returns a re-checkable counterexample when sufficiency fails | Python 3.10+, standard library only |
| [`experiment/`](experiment/) | the §9.5 study: uniform output operators on four pinned Python libraries | Python 3.10+, `uv`, `git`, network |

## 1. Proofs

```bash
cd proofs
lake exe cache get   # fetch the prebuilt Mathlib for the pinned commit
lake build           # checks every theorem, then runs the axiom audit (Audit.lean)
```

A clean build prints `Build completed successfully`. Any failure is a nonzero exit. Toolchain
`leanprover/lean4:v4.28.0`; Mathlib `v4.28.0` at commit `8f9d9cff6bd7` (pinned in `lake-manifest.json`). On
a fresh copy of this folder, the two commands above took about two minutes on an Apple Silicon laptop.

`Audit.lean` holds, for every theorem, the exact `#print axioms` output as a `#guard_msgs` expectation, so a
theorem that acquired `sorryAx` or a new axiom would fail the build rather than print a warning.

## 2. Checker

```bash
cd checker
python -m unittest test_sufficiency -v      # 8 tests, under a second
python sufficiency.py examples/example_4_4.json
```

The tests compare the decision with the definition of sufficiency exhaustively over every regime on a
three-element return type (256 regimes × 8 targets), and on 800 seeded random regimes over four and five
values; every negative answer's certificate is re-verified by running the mutants. The example prints the
counterexample for Example 4.4 and `"certificate_verified": true`.

## 3. Experiment

```bash
cd experiment
python run.py        # clones the pinned libraries into ~/.cache/knowability-experiment, then runs
python analyze.py    # prints the §9.5 tables and writes results/summary.json
```

See [`experiment/README.md`](experiment/README.md) for the design, the pins and the exclusions. The raw
per-test records the paper's numbers come from are in `experiment/results/`.
