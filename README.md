# Detective

Behavioral-scope diagnosis and warrant-classed test synthesis for a single
Python function, built on the [Wesker](https://github.com/rohanvinaik/Wesker)
mutation engine.

Detective is a clean-room port of LintGate's Detective functionality into a
self-contained package. Its workflow — diagnose a function, generate
oracle-warranted and design-warranted tests, mutation-drive them to the
ceiling — is both how the package is built and the workflow it ships (`certify`).

## Thesis

Point Detective at a function and its mutation profile tells you exactly what the
function does *and* where its behavior is left unspecified — the surviving
mutants no test distinguishes. That characterization is enough to **rebuild the
function from the ground up and make it better**: reimplement clean, then pin, as
warranted tests, precisely the degrees of freedom the original left open. You
recreate the functionality *and* raise its specification above where it started.
Detective was itself built this way — each of its modules was characterized from
its LintGate reference, reimplemented clean, and driven past the reference's own
specification ceiling.

## Install (local dev)

```
uv sync            # resolves Wesker from ../Wesker (editable)
```

## Usage

```
detective certify ./module.py::my_function
```

## Dependencies

One runtime dependency — `Wesker` — plus the standard library. No LintGate
runtime dependency.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the module layout, the build
workflow, the test architecture, and the dependency boundary.

## License

MIT © 2026 Rohan Vinaik
