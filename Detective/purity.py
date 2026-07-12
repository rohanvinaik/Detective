"""Purity analysis — does a function have observable side effects?

A focused, domain-agnostic predicate. A function is impure if it: writes a
global/nonlocal, mutates an external object (attribute, subscript, mutating
method call, or ``del``), calls an I/O builtin or a filesystem-write method, is a
generator, or has a mutable default argument. Used to gate STATE mutations and to
corroborate golden captures.

Clean-room port of LintGate's purity analyzer, scoped to the boolean Detective
needs: it drops the reference's tier/confidence ontology and its ML/DB/serializer
domain sets, and analyses a single function locally — no cross-function impurity
propagation (a documented v1 boundary).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

_IMPURE_BUILTINS = {"print", "open", "input", "exec", "eval"}
_MUTATING_METHODS = {
    "append", "extend", "insert", "remove", "pop", "clear", "update",
    "add", "discard", "sort", "reverse", "setdefault", "popitem",
}
_PATH_WRITE_METHODS = {
    "write_text", "write_bytes", "mkdir", "unlink", "rmdir", "touch", "rename", "replace",
}


@dataclass(frozen=True)
class PurityResult:
    """Whether a function is pure, and the reasons it is not."""

    is_pure: bool
    reasons: tuple[str, ...]


def get_name(node: ast.AST) -> str | None:
    """Extract a dotted name (``a``, ``a.b.c``) from a Name/Attribute node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = get_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def analyze_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef, *, is_method: bool = False
) -> PurityResult:
    """Analyse ``func`` for local side effects and return a PurityResult."""
    visitor = _SideEffectVisitor(func, is_method)
    visitor.visit(func)
    return PurityResult(not visitor.reasons, tuple(visitor.reasons))


def is_pure(func: ast.FunctionDef | ast.AsyncFunctionDef, *, is_method: bool = False) -> bool:
    """True when ``func`` has no detectable local side effects."""
    return analyze_function(func, is_method=is_method).is_pure


class _SideEffectVisitor(ast.NodeVisitor):
    def __init__(self, func: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> None:
        self.func = func
        self.is_method = is_method
        self.reasons: list[str] = []
        self.local_names = _param_names(func.args)
        self._check_mutable_defaults()

    def _external(self, name: str | None) -> bool:
        return bool(name) and name not in self.local_names  # type: ignore[return-value]

    def _mutates_instance(self, target_name: str | None) -> bool:
        return self.is_method and target_name in ("self", "cls") and self.func.name != "__init__"

    def _check_mutable_defaults(self) -> None:
        defaults = [*self.func.args.defaults, *[d for d in self.func.args.kw_defaults if d is not None]]
        if any(isinstance(d, (ast.List, ast.Dict, ast.Set, ast.Call)) for d in defaults):
            self.reasons.append("mutable default argument")

    def visit_Global(self, node: ast.Global) -> None:
        self.reasons.extend(f"writes global '{n}'" for n in node.names)
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.reasons.extend(f"writes nonlocal '{n}'" for n in node.names)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.local_names.add(target.id)
            elif isinstance(target, ast.Attribute):
                self._flag_attribute(target, "assigns")
            elif isinstance(target, ast.Subscript) and self._external(get_name(target.value)):
                self.reasons.append(f"subscript-writes external {get_name(target.value)}")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Attribute):
            self._flag_attribute(node.target, "augments")
        elif isinstance(node.target, ast.Subscript) and self._external(get_name(node.target.value)):
            self.reasons.append(f"augments external subscript {get_name(node.target.value)}")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.local_names.add(node.target.id)
        elif isinstance(node.target, ast.Attribute):
            self._flag_attribute(node.target, "assigns")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            base = target.value if isinstance(target, ast.Subscript) else target
            if self._external(get_name(base)):
                self.reasons.append(f"deletes external {get_name(base)}")
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        self.reasons.append("is a generator (yield)")
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self.reasons.append("is a generator (yield from)")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = get_name(node.func)
        if name and (name in _IMPURE_BUILTINS or name.split(".")[0] in _IMPURE_BUILTINS):
            self.reasons.append(f"calls impure builtin {name}")
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            target = get_name(node.func.value)
            if method in _MUTATING_METHODS and self._external(target):
                self.reasons.append(f"mutates external via .{method}()")
            if method in _PATH_WRITE_METHODS:
                self.reasons.append(f"filesystem write via .{method}()")
        self.generic_visit(node)

    def _flag_attribute(self, target: ast.Attribute, verb: str) -> None:
        name = get_name(target.value)
        if self._mutates_instance(name):
            self.reasons.append(f"{verb} instance state {name}.{target.attr}")
        elif self._external(name):
            self.reasons.append(f"{verb} external {name}.{target.attr}")


def _param_names(args: ast.arguments) -> set[str]:
    names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names
