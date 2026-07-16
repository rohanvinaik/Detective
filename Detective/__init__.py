"""Detective — behavioral-scope diagnosis and warrant-classed test synthesis for
a single Python function, built on the Wesker mutation engine.

Depends only on Wesker + the standard library. No lintgate runtime dependency.

Public API:
    diagnose(file, function, project_root=".")  -> ScopeMap
    certify(file, function, project_root=".", *, write_dir=None) -> CertifyResult
    converge(file, function, project_root=".", *, write_dir="tests") -> ConvergeResult
"""

from __future__ import annotations

# Keep in lockstep with pyproject's `version` — this is restated, so it drifts silently.
# Bump both, or neither. (Wesker shipped 0.3.0 announcing 0.1.0 for exactly this reason.)
__version__ = "0.4.0"

from .certify import CertifyResult, certify
from .converge import ConvergeResult, converge
from .engine import diagnose
from .scope import ScopeMap

__all__ = [
    "diagnose",
    "certify",
    "converge",
    "CertifyResult",
    "ConvergeResult",
    "ScopeMap",
    "__version__",
]
