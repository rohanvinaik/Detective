"""Decide finite output-mutation sufficiency (Theorem 3.2) and certify every negative answer.

Given a finite return type R, a finite regime Pi and a target class Gamma, each as output operators
(total maps R -> R), `decide` answers whether Pi is sufficient for Gamma: for every program and every
finite suite, a full Pi-score forces a full Gamma-score.

The answer is computed from footprints, by Theorem 3.2's condition. When the condition fails, the
answer carries a certificate built exactly as in the theorem's necessity proof: a program (the identity
on I = A + {b}) and a suite (T = A) under which every non-equivalent Pi-mutant is killed while the
target mutant g o f is non-equivalent and survives.

`verify_certificate` re-checks a certificate by running the mutants on the program. It uses only the
definitions (equivalence, killing, score) and never the footprint theorem, so it is an independent
check of a negative answer. `sufficient_by_enumeration` is the definition itself, evaluated over every
program and suite that matters on a finite R; the tests compare it with `decide`.

Standard library only. Values are any hashable Python objects; operators are dicts value -> value.
"""

from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass

Operator = dict  # value -> value, total on R


def footprint(p: Operator) -> frozenset:
    """Mov(p): the values p changes (Definition 2.2)."""
    return frozenset(r for r, v in p.items() if v != r)


@dataclass(frozen=True)
class Certificate:
    """A program and suite on which Pi scores 1 and the target g does not (Theorem 3.2, necessity)."""

    target: str  # name of g in Gamma
    uncovered_value: object  # b in Mov(g): no Pi-footprint contains b and stays inside Mov(g)
    escapes: dict  # for each p in Pi that moves b, its escape value a_p in Mov(p) \ Mov(g)
    domain: list  # D = I = A + {b}; the program is the identity f(x) = x on D
    suite: list  # T = A, so the observed outputs are O = A


@dataclass(frozen=True)
class Result:
    sufficient: bool
    certificate: Certificate | None = None


def _check_total(R: list, ops: dict) -> None:
    rs = set(R)
    for name, p in ops.items():
        if set(p) != rs or not set(p.values()) <= rs:
            raise ValueError(f"operator {name!r} is not a total map R -> R")


def decide(R: list, Pi: dict, Gamma: dict) -> Result:
    """Theorem 3.2: Pi (finite) is sufficient for Gamma iff every b in Mov(g), for every g in Gamma,
    lies in some Mov(p), p in Pi, with Mov(p) contained in Mov(g)."""
    _check_total(R, Pi)
    _check_total(R, Gamma)
    feet = {name: footprint(p) for name, p in Pi.items()}
    for gname, g in Gamma.items():
        mg = footprint(g)
        for b in R:  # iterate in R's order so the certificate is deterministic
            if b not in mg:
                continue
            if any(b in s and s <= mg for s in feet.values()):
                continue
            # The condition fails at (g, b): every Pi-footprint through b escapes Mov(g).
            escapes = {}
            for pname, s in feet.items():
                if b in s:
                    escapes[pname] = next(a for a in R if a in s and a not in mg)
            A = list(dict.fromkeys(escapes.values()))  # distinct, in a fixed order
            return Result(False, Certificate(gname, b, escapes, A + [b], A))
    return Result(True)


def _score_one(ops: dict, f: dict, suite: list) -> bool:
    """score = 1: every non-equivalent mutant p o f is killed by some test (Definition 2.3)."""
    for p in ops.values():
        equivalent = all(p[f[x]] == f[x] for x in f)
        killed = any(p[f[x]] != f[x] for x in suite)
        if not equivalent and not killed:
            return False
    return True


def verify_certificate(R: list, Pi: dict, Gamma: dict, cert: Certificate) -> bool:
    """Run the certificate's program and suite: Pi must score 1 and the target must not.
    Uses only Definition 2.3, never footprints or Theorem 3.2."""
    rs = set(R)
    if not set(cert.domain) <= rs or not set(cert.suite) <= set(cert.domain):
        return False
    f = {x: x for x in cert.domain}  # the identity program on D
    g = Gamma[cert.target]
    target_survives = not _score_one({cert.target: g}, f, cert.suite)
    return _score_one(Pi, f, cert.suite) and target_survives


def sufficient_by_enumeration(R: list, Pi: dict, Gamma: dict) -> bool:
    """Definition 3.1 evaluated directly. By Proposition 2.4 a program enters only through its
    reachable set I and observed set O <= I, and every such pair is realized by the identity on I with
    suite O; so ranging over all pairs O <= I <= R covers every program and suite."""
    for k in range(1, len(R) + 1):
        for reach in itertools.combinations(R, k):
            f = {x: x for x in reach}
            for j in range(len(reach) + 1):
                for observed in itertools.combinations(reach, j):
                    if _score_one(Pi, f, list(observed)) and not _score_one(Gamma, f, list(observed)):
                        return False
    return True


def operator_with_footprint(R: list, S) -> Operator:
    """Remark 2.5: an operator whose footprint is exactly S (needs |R| >= 2)."""
    a, b = R[0], R[1]
    return {x: ((b if x == a else a) if x in S else x) for x in R}


def constant(R: list, c) -> Operator:
    return {x: c for x in R}


def main(argv: list[str]) -> int:
    """CLI: `python sufficiency.py problem.json` prints the decision, and the certificate if any.
    The problem file holds {"R": [...], "Pi": {name: {value: value}}, "Gamma": {...}}; JSON object
    keys are strings, so values are compared as strings."""
    if len(argv) != 2:
        print(main.__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        prob = json.load(fh)
    R = [str(r) for r in prob["R"]]
    Pi = {n: {str(k): str(v) for k, v in p.items()} for n, p in prob["Pi"].items()}
    Gamma = {n: {str(k): str(v) for k, v in p.items()} for n, p in prob["Gamma"].items()}
    res = decide(R, Pi, Gamma)
    out: dict[str, object] = {"sufficient": res.sufficient}
    if res.certificate is not None:
        out["certificate"] = asdict(res.certificate)
        out["certificate_verified"] = verify_certificate(R, Pi, Gamma, res.certificate)
    print(json.dumps(out, indent=2))
    return 0 if res.sufficient else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
