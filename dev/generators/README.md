# dev/generators — dev-time oracle test generators

These scripts (`gen_<module>_oracle_tests.py`) run the **reference behavior** —
LintGate's working implementation, imported here as a *dev-time conformance
oracle only* — over an input corpus and emit static, parametrized, do-not-hand-
edit `tests/test_<module>_oracle.py` files with the expected values baked in as
literals.

This tree is **not part of the shipped package** (excluded from the wheel in
`pyproject.toml`). LintGate therefore never enters Detective's runtime import
graph: it is used once, at generation time, to certify conformance — exactly how
Regenesis uses `genesis.jar`. The generated test files contain only literals.
