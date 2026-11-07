# Sufficiency checker (Theorem 3.2, executable)

`sufficiency.py` decides whether a finite output-mutation regime `Π` is sufficient for a target class `Γ`
on a finite return type `R`: whether, for every program and every finite suite, a full `Π`-score forces a
full `Γ`-score.

- `decide(R, Pi, Gamma)` applies Theorem 3.2's condition to the operators' footprints. When the condition
  fails at a target `g` and value `b`, it returns the necessity proof's counterexample: for each `p ∈ Π`
  that moves `b`, an escape value `a_p ∈ Mov(p) \ Mov(g)`; then `A = {a_p}`, the program is the identity on
  `D = I = A ∪ {b}`, and the suite is `T = A`.
- `verify_certificate` runs every mutant on that program and suite using only the definitions of
  equivalence, killing and score (never footprints), and confirms that `Π` scores one while `g` survives.
- `sufficient_by_enumeration` evaluates the definition of sufficiency directly over all reachable/observed
  pairs; the tests check that it agrees with `decide`.

Operators are total maps given as dicts. Standard library only.

```bash
python -m unittest test_sufficiency -v
python sufficiency.py examples/example_4_4.json   # exit status 1: not sufficient; certificate printed
```
