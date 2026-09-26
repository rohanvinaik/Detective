"""Can a renamed field be absorbed into a silent default — §9 invariant 7's second clause.

`docs/theory/COMMUNICATING_DETERMINISM.md` §9:

    7. An unmeasured input votes zero, and no `getattr(obj, name, default)` stands where a renamed
       field could be absorbed into a silent clean verdict.

A `getattr` with a default is the one attribute read a rename cannot break loudly. Its name is a
string literal, so the reference graph cannot see it (the consumption guard, Serena and ty all look
past it), and after a rename the default answers forever. Measured when this was built: 251 such
reads in the package, 47 of them reading a fault flag (`budget_exhausted`, `load_failed`,
`stale_target`, …) with a default that means "no problem", 37 of those in the renderers. Rename the
field and the report goes quietly clean.

THE CHECK. Every literal name a `getattr(..., default)` reads must be DECLARED by something: a field,
method, property or class attribute of a class in Detective or Wesker; an attribute stored on any
object there (Detective stashes three on Wesker's `ProfilingResult`); an option of the CLI parser; a
node field of `ast`; or the Python data model (a dunder). A name nothing declares is a default that
can only ever be its default — a rename already absorbed, or a typo. What is declared outside all of
those takes a written reason, as in the sibling guards.

KNOWN LIMIT, stated rather than papered over: "declared by something" is not "declared by this
object's type". A name several classes declare (`budget_exhausted` is on three) survives a rename on
one of them. Closing that needs the object's static type at each read, which the AST does not have.

Deliberately NOT wired into any verb, like `consumption.py` and `distinction.py`.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

DECLARED = "declared"
DATA_MODEL = "data_model"
EXTERNAL_DECLARED = "external_declared"
EXTERNAL_STALE = "external_stale"
UNDECLARED = "undeclared"


def absorption_disposition(declared: bool, dunder: bool, external_reason: str) -> str:
    """Whether a `getattr(obj, name, default)` could be reading a name that no longer exists
    (§9 invariant 7, pure — pinned).

    Named codes, because each is a different fact about the read and a different remedy:

      "declared"           something in the pair declares the name: a rename there takes it away,
                           and this read then reports as `undeclared`. Nothing to answer.
      "data_model"         a dunder (`__code__`, `__wrapped__`): declared by the language.
      "external_declared"  declared outside the pair (a Python-version-dependent `ast` or `sys`
                           attribute, a CPython object's field), and a reason on record says by whom.
      "external_stale"     a reason is on record, but the pair declares the name now. The entry
                           outlived its reason and should be DELETED.
      "undeclared"         nothing declares it and nothing says why: THE finding. The default is
                           the only value this read can ever produce.

    An empty or whitespace-only reason is not a reason, the same rule the sibling guards apply.
    """
    if declared:
        return EXTERNAL_STALE if external_reason.strip() else DECLARED
    if dunder:
        return DATA_MODEL
    if external_reason.strip():
        return EXTERNAL_DECLARED
    return UNDECLARED


@dataclass(frozen=True)
class GetattrRead:
    """One `getattr(obj, "name", default)` with a literal name."""

    location: str  # "path:line"
    function: str  # the innermost enclosing function, "" at module level
    name: str
    default: str  # the default's source text

    @property
    def dunder(self) -> bool:
        return self.name.startswith("__") and self.name.endswith("__")


def getattr_reads(package_dir: str) -> list[GetattrRead]:
    """Every three-argument `getattr` with a string-literal name under `package_dir`, in file order.
    A two-argument `getattr` raises on a missing name — loud already — and is not collected."""
    reads: list[GetattrRead] = []
    for path, tree in _parsed(package_dir):
        for function, node in _calls_with_function(tree):
            if not (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) == 3):
                continue
            name = node.args[1]
            if isinstance(name, ast.Constant) and isinstance(name.value, str):
                default = ast.unparse(node.args[2])
                reads.append(GetattrRead(f"{path}:{node.lineno}", function, name.value, default))
    return reads


def declared_attributes(*roots: str) -> frozenset[str]:
    """Every attribute name the code under `roots` declares: a class body's annotated or assigned
    names and its methods (properties included), and every attribute stored on ANY object —
    `self.x = …`, a stash like `result.measurement_basis = …`, or `setattr(obj, "x", …)`."""
    names: set[str] = set()
    for root in roots:
        for _path, tree in _parsed(root):
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    names |= _class_body_names(node)
                elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                    names.add(node.attr)
                elif isinstance(node, ast.Call) and (stored := _setattr_literal(node)) is not None:
                    names.add(stored)
    return frozenset(names)


def ast_node_fields() -> frozenset[str]:
    """The field and attribute names of every `ast` node class in THIS interpreter."""
    out: set[str] = set()
    for value in vars(ast).values():
        if isinstance(value, type) and issubclass(value, ast.AST):
            # `ast.AST` itself declares both, so every node class has them: read them directly —
            # a defaulted getattr here would be the very read this module exists to fence.
            out |= set(value._fields) | set(value._attributes)
    return frozenset(out)


# ---------------------------------------------------------------- the gathering layer (impure)


def _parsed(root: str) -> list[tuple[pathlib.Path, ast.Module]]:
    out = []
    for path in sorted(pathlib.Path(root).rglob("*.py")):
        if ".lake" in path.parts:
            continue
        try:
            out.append((path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
    return out


def _calls_with_function(tree: ast.Module):
    """(innermost enclosing function name, call) for every call in the module."""
    stack: list[tuple[ast.AST, str]] = [(tree, "")]
    while stack:
        node, function = stack.pop()
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            if isinstance(child, ast.Call):
                yield inner, child
            stack.append((child, inner))


def _class_body_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            names.add(statement.target.id)
        elif isinstance(statement, ast.Assign):
            names |= {t.id for t in statement.targets if isinstance(t, ast.Name)}
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(statement.name)
    return names


def _setattr_literal(node: ast.Call) -> str | None:
    """The name `setattr(obj, "name", value)` stores, when it is a literal."""
    if isinstance(node.func, ast.Name) and node.func.id == "setattr" and len(node.args) >= 2:
        name = node.args[1]
        if isinstance(name, ast.Constant) and isinstance(name.value, str):
            return name.value
    return None
