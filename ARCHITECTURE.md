# Detective — Architecture

Functional/technical reference. Detective is a **clean-room port** of LintGate's
Detective functionality into a self-contained package on Wesker + stdlib.

Hard constraints (the design):

- **Product-grade**, not "something that works".
- **Proper, idiomatic pytest** throughout — including the tests Detective
  *auto-generates* when run (parametrized, fixtured, correctly placed/named).
- **No LintGate runtime dependency** and **no LintGate tool-calling** in the
  shipped package.
- **No literal copy of LintGate code** — behavior is the spec, the code is fresh.
- **Runtime dependencies: Wesker + stdlib only.**

---

## 0. Thesis (the method, stated once)

A function's mutation profile is a complete map of the behavioral distinctions it
makes: killed mutants = distinctions the tests pin, survivors = degrees of freedom
no test distinguishes. That map is enough to **recreate the functionality and make
it better** — reimplement clean against the observed behavior, then pin the
survivors the original left unspecified as warranted tests. The port therefore
does not merely match the reference; it drives the reimplementation *past the
reference's own specification ceiling*. Every Detective module is built this way,
including Detective's own (characterized from its LintGate reference, then
certified higher).

## 1. The workflow (build process AND shipped product)

Per unit — whether we are building Detective or a Detective user is certifying
their own function — the same loop, two warrant classes in separate pytest files
so each assertion's warrant is legible:

- **Oracle-warranted** (`test_<mod>_oracle.py`) — expected values come from a
  reference oracle, emitted by a `gen_<mod>_oracle_tests.py` generator. Static,
  parametrized, do-not-hand-edit.
- **Design-warranted / native** (`test_<mod>_native.py`) — behavior with no
  oracle equivalent (or an intentional deviation); each case's docstring states
  its warrant.

Then the **Wesker mutation loop**: profile the unit → each *meaningful* survivor
becomes a warranted test that kills it → dead/unreachable code is *simplified*,
not tested → reset between runs → stop at 100% or the equivalent-mutant /
`LOW_CONFIDENCE` ceiling. A survivor is a prescription, not a nuisance. A unit is
**done only at the ceiling** — never on copy-paste.

`certify` orchestrates this loop as the product's front door; the **CLI** and an
**MCP** are thin wrappers over it (zero compute in either wrapper).

### Auto-generation hygiene (product invariant)

When Detective runs, the tests it writes MUST be clean, idiomatic, well-organized
pytest: parametrized oracle files, warrant-docstring native files, correct
`tests/` placement and `test_<mod>_{oracle,native}.py` naming, fixtures in
`conftest.py`. Detective does not inherit any harness conventions from Wesker
(whose own suite is intentionally minimal); it sets its own bar.

---

## 2. Oracle policy (per module)

- **Reference/port modules** (`scope`, `decompose`, format-defined output):
  LintGate's working implementation is the **dev-time conformance oracle** —
  imported only inside `dev/generators/*`, never shipped.
- **Synthesis modules** (`oracle_light`, `characterization`, `typed_synthesis`,
  `writer`): **Wesker is the self-oracle** — a synthesized test is correct iff it
  kills its target mutant. No external oracle needed.
- **First-principles modules** (`purity`): a documented spec / labeled corpus
  pins behavior directly.

`dev/generators/` is excluded from the wheel, so LintGate never enters the
runtime import graph.

---

## 3. Module DAG (build + certify in this order)

```
scope        pure reshaper of a Wesker profiling result → behavioral-scope map
discovery    locate the real tests that exercise a function (ast + sqlite cache)
purity       purity analysis (STATE-mutation gating / regime inputs)
engine       Wesker adapter (resolve fn → profile → result); needs scope + discovery
synthesis/   oracle_light · characterization · typed_synthesis · writer
decompose    entangled-function split plan (AST slicing)
certify      the loop orchestrator — the product spine
cli · mcp    thin surfaces, zero compute
```

Each unit is built clean, then certified through the workflow (§1) before the
next begins. Bootstrap runs the loop on **Wesker directly**; once `certify` is
certified, Detective self-hosts.

---

## 4. Test architecture (Detective's own suite)

```
tests/
  conftest.py                 shared fixtures (corpus loaders, tmp-project, Wesker profile)
  fixtures/                   input corpora
  test_<mod>_oracle.py        GENERATED, parametrized, do-not-hand-edit
  test_<mod>_native.py        design-warranted, warrant docstrings
dev/generators/
  gen_<mod>_oracle_tests.py   dev-only; imports LintGate as oracle; NOT shipped
```

`[tool.pytest.ini_options]` sets `testpaths`, naming, and strict markers/config.
CI: pytest + coverage + ruff + a Wesker self-profile gate.

---

## 5. Dependency boundary

Runtime: **Wesker + stdlib only** (the sole non-stdlib import in any vendored
concept is `sqlite3`, for the discovery linkage cache — stdlib). Dev-only:
pytest, pytest-cov, ruff, and the LintGate import confined to `dev/generators/`.

---

## 6. Build status

- Phase 0 — foundation/scaffolding: in progress.
- Phase 1+ — units built + certified in DAG order (§3), each reviewable.
