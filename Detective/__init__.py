"""Detective — behavioral-scope diagnosis and warrant-classed test synthesis for
a single Python function, built on the Wesker mutation engine.

Depends only on Wesker + the standard library. No lintgate runtime dependency.

Public API:
    diagnose(file, function, project_root=".")  -> ScopeMap
    certify(file, function, project_root=".", *, write_dir=None) -> CertifyResult
    converge(file, function, project_root=".", *, write_dir="tests") -> ConvergeResult
"""

from __future__ import annotations

# THE one owner of this number. `pyproject.toml` declares `dynamic = ["version"]` and
# `[tool.hatch.version] path = "Detective/__init__.py"`, so the build reads it from HERE — bump
# this and nothing else. (This comment used to say "keep in lockstep with pyproject's version —
# this is restated", which was true until the number moved here. Following it now would put a
# second copy back in pyproject and recreate the drift going dynamic removed: 0.3.0 shipped to
# PyPI announcing `detective --version 0.2.0`.)
__version__ = "0.8.1"

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
