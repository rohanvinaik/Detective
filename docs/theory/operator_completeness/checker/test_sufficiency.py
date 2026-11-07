"""Tests for the sufficiency checker: the decision must agree with the definition, and every negative
answer must come with a certificate that independently re-checks.

Run from this folder:  python -m unittest test_sufficiency -v
"""

from __future__ import annotations

import itertools
import random
import unittest

from sufficiency import (
    constant,
    decide,
    footprint,
    operator_with_footprint,
    sufficient_by_enumeration,
    verify_certificate,
)


def all_footprints(R):
    return [frozenset(c) for k in range(len(R) + 1) for c in itertools.combinations(R, k)]


def cert_of(res):
    assert res.certificate is not None, "a negative answer must carry a certificate"
    return res.certificate


def regime(R, feet, prefix):
    return {f"{prefix}{i}": operator_with_footprint(R, s) for i, s in enumerate(feet)}


class TestAgreesWithDefinition(unittest.TestCase):
    def test_exhaustive_three_values(self):
        """Every regime of footprints on |R| = 3 (all 256) against every single target (8):
        decide == the definition, and every certificate verifies."""
        R = ["a", "b", "c"]
        feet = all_footprints(R)
        checked = 0
        for mask in range(1 << len(feet)):
            Pi = regime(R, [s for i, s in enumerate(feet) if mask >> i & 1], "p")
            for t in feet:
                Gamma = {"g": operator_with_footprint(R, t)}
                res = decide(R, Pi, Gamma)
                self.assertEqual(res.sufficient, sufficient_by_enumeration(R, Pi, Gamma))
                if not res.sufficient:
                    self.assertTrue(verify_certificate(R, Pi, Gamma, cert_of(res)))
                checked += 1
        self.assertEqual(checked, 256 * 8)

    def test_random_larger_codomains(self):
        """Seeded random regimes, targets and operators (not only the Remark 2.5 shape) on |R| = 4, 5."""
        rng = random.Random(20261106)
        for n in (4, 5):
            R = [f"v{i}" for i in range(n)]
            for _ in range(400):
                Pi = {f"p{i}": {x: rng.choice(R) for x in R} for i in range(rng.randint(0, 5))}
                Gamma = {f"g{i}": {x: rng.choice(R) for x in R} for i in range(rng.randint(1, 3))}
                res = decide(R, Pi, Gamma)
                self.assertEqual(res.sufficient, sufficient_by_enumeration(R, Pi, Gamma))
                if not res.sufficient:
                    self.assertTrue(verify_certificate(R, Pi, Gamma, cert_of(res)))


class TestPaperExamples(unittest.TestCase):
    R = ["a", "b", "c"]

    def test_example_4_4_constants_on_three_values(self):
        """Example 4.4: the three constants are not sufficient for the guard on c."""
        Pi = {f"return {c}": constant(self.R, c) for c in self.R}
        Gamma = {"guard c": operator_with_footprint(self.R, {"c"})}
        res = decide(self.R, Pi, Gamma)
        self.assertFalse(res.sufficient)
        cert = cert_of(res)
        self.assertEqual(cert.uncovered_value, "c")
        self.assertTrue(verify_certificate(self.R, Pi, Gamma, cert))
        # reachable {a, b, c}, observed {a, b}: every constant dies, the guard survives
        self.assertEqual(set(cert.domain), {"a", "b", "c"})
        self.assertEqual(set(cert.suite), {"a", "b"})

    def test_corollary_4_1_value_guards_are_absolutely_sufficient(self):
        Pi = {f"guard {r}": operator_with_footprint(self.R, {r}) for r in self.R}
        every = {
            f"op{i}": dict(zip(self.R, img, strict=True))
            for i, img in enumerate(itertools.product(self.R, repeat=3))
        }
        self.assertTrue(decide(self.R, Pi, every).sufficient)

    def test_corollary_4_3_constants_sufficient_on_booleans(self):
        R = [False, True]
        Pi = {f"return {c}": constant(R, c) for c in R}
        every = {
            f"op{i}": dict(zip(R, img, strict=True)) for i, img in enumerate(itertools.product(R, repeat=2))
        }
        self.assertTrue(decide(R, Pi, every).sufficient)

    def test_section_7_one_subsuming_footprint_is_insufficient(self):
        R = [0, 1, 2]
        Pi = {"p": operator_with_footprint(R, {0})}
        Gamma = {"g": operator_with_footprint(R, {0, 1})}
        res = decide(R, Pi, Gamma)
        self.assertFalse(res.sufficient)
        self.assertEqual(cert_of(res).uncovered_value, 1)
        self.assertTrue(verify_certificate(R, Pi, Gamma, cert_of(res)))


class TestVerifierIsNotARubberStamp(unittest.TestCase):
    def test_rejects_a_tampered_certificate(self):
        R = ["a", "b", "c"]
        Pi = {f"return {c}": constant(R, c) for c in R}
        Gamma = {"guard c": operator_with_footprint(R, {"c"})}
        cert = cert_of(decide(R, Pi, Gamma))
        # observing c as well kills the guard, so this is no longer a counterexample
        tampered = type(cert)(cert.target, cert.uncovered_value, cert.escapes, cert.domain, cert.domain)
        self.assertFalse(verify_certificate(R, Pi, Gamma, tampered))

    def test_footprint(self):
        self.assertEqual(footprint({0: 1, 1: 1, 2: 0}), frozenset({0, 2}))


if __name__ == "__main__":
    unittest.main()
