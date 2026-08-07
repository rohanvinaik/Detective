"""Target binding — how a target is CALLED, and how its receiver is constructed (issue #25).

A free function is called ``f(*args)``; a method is not. Detective loaded the unbound function and
called it with the synthesized inputs positionally, so ``self`` was fed a grid value and every call
raised — reported as ``0/N killed`` where a named refusal belonged. This module classifies the target
from the AST (function / static / class / instance method / property) and, for an instance method,
resolves a RECEIVER PLAN: a factory that builds a fresh receiver per call, plus the source form the
generated test uses to reconstruct it. The receiver is a separate proof axis from the arguments —
never an ``--input`` — so a single ``Basket()`` scopes the certificate to the receiver population
actually explored, exactly as the operator universe scopes the mutation claim.
"""

from __future__ import annotations

import ast
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class BindingKind(StrEnum):
    FUNCTION = "function"
    STATIC_METHOD = "static_method"
    CLASS_METHOD = "class_method"
    INSTANCE_METHOD = "instance_method"
    PROPERTY = "property"  # refused by name — a property has no call signature to synthesize
    UNSUPPORTED = "unsupported"  # a custom/unknown descriptor — refused, never guessed


@dataclass(frozen=True)
class TargetBinding:
    """How the target is invoked. ``owner`` is the class qualname for a method, else "".

    ``receiver_params`` is how many LEADING ast parameters are the receiver (``self``/``cls``), which
    input synthesis must skip: 1 for an instance or class method, 0 for a function or static method.
    A bound classmethod object already supplies ``cls`` (so the callable takes args-minus-cls); an
    instance method's UNBOUND function still takes ``self`` first (so a receiver is prepended)."""

    kind: BindingKind
    owner: str
    attribute: str
    receiver_params: int


def classify_binding_kind(
    decorators: tuple[str, ...], in_class: bool, first_param: str | None
) -> BindingKind:
    """The binding kind from three AST facts (issue #25, pure — Detective-pinned).

    ``@property`` (or a known descriptor) is refused by name — it has no call signature to
    synthesize. Otherwise: a ``@staticmethod`` is function-like; a ``@classmethod`` binds ``cls``; a
    def inside a class whose first parameter is ``self`` (or ``cls`` without the decorator, treated as
    an instance receiver) is an instance method; anything else is a free function. Order matters —
    property is checked before the method kinds so a property never reads as an instance method.
    """
    if "property" in decorators or "cached_property" in decorators:
        return BindingKind.PROPERTY
    if not in_class:
        return BindingKind.FUNCTION
    if "staticmethod" in decorators:
        return BindingKind.STATIC_METHOD
    if "classmethod" in decorators:
        return BindingKind.CLASS_METHOD
    if first_param in ("self", "cls"):
        return BindingKind.INSTANCE_METHOD
    # A method with no receiver parameter and no @staticmethod is malformed for our purposes; treat
    # it as unsupported rather than silently calling it wrong.
    return BindingKind.UNSUPPORTED


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    names: list[str] = []
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            names.append(d.id)
        elif isinstance(d, ast.Attribute):
            names.append(d.attr)
    return tuple(names)


def classify_target(tree: ast.Module, qualname: str) -> TargetBinding:
    """Resolve ``qualname`` ("fn" or "Owner.method") to a :class:`TargetBinding` by walking the AST.

    Only one level of class nesting is supported (``Owner.method``); a deeper qualname or an
    unresolvable one yields UNSUPPORTED, a named refusal rather than a wrong call.
    """
    if "." not in qualname:
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == qualname:
                return TargetBinding(BindingKind.FUNCTION, "", qualname, 0)
        return TargetBinding(BindingKind.UNSUPPORTED, "", qualname, 0)

    owner_name, _, attr = qualname.partition(".")
    for cls in tree.body:
        if not (isinstance(cls, ast.ClassDef) and cls.name == owner_name):
            continue
        for m in cls.body:
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == attr:
                decs = _decorator_names(m)
                first = m.args.args[0].arg if m.args.args else None
                kind = classify_binding_kind(decs, in_class=True, first_param=first)
                recv = 1 if kind in (BindingKind.INSTANCE_METHOD, BindingKind.CLASS_METHOD) else 0
                return TargetBinding(kind, owner_name, attr, recv)
    return TargetBinding(BindingKind.UNSUPPORTED, owner_name, attr, 0)


@dataclass(frozen=True)
class ReceiverPlan:
    """How to build a receiver for an instance-method call, and how to render it in a test.

    ``factory`` builds a FRESH receiver each call (soundness: no mutable receiver is reused across the
    two determinism checks, and original and mutant see the identical plan). ``render`` is the source
    the emitted test uses to reconstruct it (``Owner()`` or ``pkg.mod:make()``). ``identity`` goes into
    cache keys / pins / receipts so a certificate is scoped to the receiver population it explored.
    """

    factory: Callable[[], Any]
    render: str
    identity: str


def resolve_receiver_plan(
    owner_cls: Any, owner_name: str, factory_spec: Callable[[], Any] | None, factory_render: str | None
) -> ReceiverPlan | None:
    """Acquire a receiver by strict evidence order (issue #25). Returns None → ``needs-receiver``.

    1. an explicit ``--receiver-factory`` (highest — the user named the construction);
    2. a contained, successful zero-argument ``Owner()``;
    otherwise None, which the caller turns into a ``needs-receiver`` refusal — never "0 kills".
    (Evidence order #1 in the design, "a receiver observed in a covering test", is handled by the
    EXISTING flow: a covering test already constructs the receiver and Wesker profiles against it, so
    it never reaches synthesis. This resolves the NO-covering-test case.)
    """
    if factory_spec is not None:
        return ReceiverPlan(factory_spec, factory_render or f"{owner_name}()", f"factory:{factory_render}")
    if owner_cls is None:
        return None
    with contextlib.suppress(Exception):
        owner_cls()  # probe: does a zero-arg construction succeed? (contained; discarded)
        return ReceiverPlan(owner_cls, f"{owner_name}()", f"zero-arg:{owner_name}")
    return None


def call_expr_and_import(binding: TargetBinding, plan: ReceiverPlan | None) -> tuple[str, str]:
    """The source the generated test uses to CALL the target, and the name it must import (#25).

    * function        -> ``fn(...)``            import ``fn``
    * static / class  -> ``Owner.method(...)``  import ``Owner`` (cls is auto-bound; no receiver)
    * instance        -> ``Owner().method(...)``import ``Owner`` — a FRESH receiver per assertion,
      exactly the soundness rule the live capture obeys; ``plan.render`` supplies ``Owner()`` or a
      ``--receiver-factory`` expression.

    Returns ``(call_expr, import_name)`` where ``call_expr`` is everything before the ``(``.
    """
    if binding.kind is BindingKind.FUNCTION:
        return binding.attribute, binding.attribute
    if binding.kind in (BindingKind.STATIC_METHOD, BindingKind.CLASS_METHOD):
        return f"{binding.owner}.{binding.attribute}", binding.owner
    if binding.kind is BindingKind.INSTANCE_METHOD and plan is not None:
        return f"{plan.render}.{binding.attribute}", binding.owner
    # PROPERTY / UNSUPPORTED / instance-without-plan never render — the caller refuses first.
    return binding.attribute, binding.owner or binding.attribute


def strip_receiver_args(node: ast.FunctionDef | ast.AsyncFunctionDef, n: int):
    """A shallow copy of ``node`` whose first ``n`` positional args (``self``/``cls``) are removed, so
    input synthesis generates values for the REAL arguments only. The body is shared (never mutated);
    only the signature the synthesizer reads changes. ``n==0`` returns the node unchanged."""
    if n <= 0:
        return node
    a = node.args
    new_args = ast.arguments(
        posonlyargs=list(a.posonlyargs),
        args=list(a.args)[n:],
        vararg=a.vararg,
        kwonlyargs=list(a.kwonlyargs),
        kw_defaults=list(a.kw_defaults),
        kwarg=a.kwarg,
        defaults=list(a.defaults),
    )
    clone = ast.FunctionDef(
        name=node.name,
        args=new_args,
        body=node.body,
        decorator_list=[],
        returns=node.returns,
        type_comment=None,
    )
    return ast.copy_location(clone, node)
