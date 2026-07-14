"""Detective — behavioral-scope diagnosis and warrant-classed test synthesis for
a single Python function, built on the Wesker mutation engine.

Depends only on Wesker + the standard library. No lintgate runtime dependency.

Public API:
    diagnose(file, function, project_root=".")  -> ScopeMap
    certify(file, function, project_root=".", *, write_dir=None) -> CertifyResult
    converge(file, function, project_root=".", *, write_dir="tests") -> ConvergeResult
"""

from __future__ import annotations

__version__ = "0.1.0"

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
