"""Test synthesis — the auto-write half of the workflow.

Modules:
- characterization: golden-capture tests for deterministic functions.
- (oracle_light, typed_synthesis, writer land here as the cluster is ported.)

Correctness oracle for this cluster is Wesker itself: a synthesized test is
correct iff it kills the mutant it targets. Reimplemented clean from LintGate's
references, improving the seams (capture is separated from resolution).
"""

from __future__ import annotations
