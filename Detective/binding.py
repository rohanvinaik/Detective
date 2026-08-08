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
import inspect
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


# ── Execution binding ─────────────────────────────────────────────
# The classification above says HOW a target is called; the machinery below turns that into a
# CALLABLE the existing synthesis/capture/witness code can invoke exactly like a free function.
# The whole point of #25: `_load_original` hands back the UNBOUND method, and every synthesis path
# already strips `self`/`cls` from the parameters (`representative_site`, `_input_grids`,
# `_kwargs_names`), so the arguments are receiver-free — what is missing is a receiver PREPENDED at
# call time. A receiver-bound wrapper supplies it, symmetrically for the original and every mutant.


def binding_from_node(node: ast.AST, qualname: str) -> TargetBinding:
    """The :class:`TargetBinding` from a resolved FunctionDef ``node`` + its ``qualname``.

    The call sites already hold ``node`` (from ``_resolve``) and ``qualname``, so classifying from
    them avoids re-parsing the whole module that :func:`classify_target` would. Only one level of
    class nesting is modelled (``Owner.method``); a deeper owner yields a plan that cannot resolve
    and becomes a named ``needs-receiver`` refusal downstream, never a wrong call.
    """
    if "." not in qualname:
        return TargetBinding(BindingKind.FUNCTION, "", qualname, 0)
    owner, _, attr = qualname.rpartition(".")
    decs = _decorator_names(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ()
    args = getattr(node, "args", None)
    first = args.args[0].arg if (args and args.args) else None
    kind = classify_binding_kind(decs, in_class=True, first_param=first)
    recv = 1 if kind in (BindingKind.INSTANCE_METHOD, BindingKind.CLASS_METHOD) else 0
    return TargetBinding(kind, owner, attr, recv)


def _unwrap_descriptor(fn: Any) -> Any:
    """The underlying function of a ``classmethod``/``staticmethod`` descriptor object, else ``fn``.

    ``_compile_mutant`` execs the mutated ``def`` node WITH its decorator list, so a mutant of a
    classmethod/staticmethod comes back as the descriptor OBJECT (not callable standalone). The
    original loaded via ``getattr`` is already unwrapped for a staticmethod but still bound for a
    classmethod; :func:`underlying_function` handles that side. This unwraps the mutant side so both
    reach the same raw ``(receiver, *args)`` function and are called identically."""
    if isinstance(fn, (classmethod, staticmethod)):
        return fn.__func__
    return fn


def underlying_function(live: Any, binding: TargetBinding) -> Any:
    """The raw ``(receiver, *args)`` function for BOTH original and mutant to share a call convention.

    A classmethod attribute (``getattr(Owner, "make")``) is a BOUND method — ``cls`` is auto-supplied,
    so calling it with the receiver-free grid args passes ``cls`` a real argument and the arities
    disagree with the unbound mutant the compiler produces. ``.__func__`` is the raw ``(cls, *args)``
    function, symmetric with that mutant. An instance-method attribute is already the unbound function
    in Py3; a staticmethod/function likewise. Returns ``live`` unchanged when there is nothing to
    unwrap."""
    if binding.kind is BindingKind.CLASS_METHOD:
        return getattr(live, "__func__", live)
    return _unwrap_descriptor(live)


def _receiver_stripped_signature(fn: Any) -> inspect.Signature | None:
    """``fn``'s signature with its FIRST parameter (the receiver ``self``/``cls``) removed, or None.

    The receiver-bound wrapper below must carry THIS as ``__signature__`` so ``_binds`` — which
    guards the witness search with ``inspect.signature(fn).bind(*args)`` — still checks the REAL
    argument arity. A bare ``*args`` wrapper would make ``_binds`` vacuously true and reintroduce the
    exact fabricated-witness bug (a mis-arity call read as the function's behaviour) that guard
    exists to prevent. None when the signature is unreadable (a builtin) — then the wrapper carries
    no ``__signature__`` and ``_binds`` falls back to its permissive "unknown signature → True"."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    params = list(sig.parameters.values())
    return sig.replace(parameters=params[1:]) if params else sig


class ReceiverBound:
    """A callable that PREPENDS a fresh receiver to every call, so an unbound method reads as a free
    function to the synthesis/capture/witness code that calls it.

    Soundness (the #25 requirements): ``make_receiver`` is invoked PER CALL, so no mutable receiver is
    reused across the two determinism checks, and the identical plan runs for original and mutant. The
    wrapper exposes:

    * ``__signature__`` = the underlying signature minus the receiver param, so ``_binds`` still
      checks the real arity (see :func:`_receiver_stripped_signature`);
    * ``__globals__`` = the underlying's, so ``_compile_mutant`` — which seeds a mutant's namespace
      from ``original.__globals__`` — still resolves the target module's siblings even if a caller
      passes a wrapped original (the call sites keep the UNBOUND original for compilation, but this
      keeps the wrapper honest either way).
    """

    def __init__(self, fn: Callable[..., Any], make_receiver: Callable[[], Any]) -> None:
        self._fn = fn
        self._make = make_receiver
        self.__globals__ = getattr(fn, "__globals__", {})  # type: ignore[attr-defined]
        self.__name__ = getattr(fn, "__name__", "receiver_bound")
        self.__qualname__ = getattr(fn, "__qualname__", self.__name__)
        sig = _receiver_stripped_signature(fn)
        if sig is not None:
            self.__signature__ = sig  # consumed by inspect.signature → _binds arity check

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._fn(self._make(), *args, **kwargs)


def wrap_callable(fn: Any, make_receiver: Callable[[], Any] | None) -> Any:
    """Receiver-bind ``fn`` when the target has a receiver, else return it unchanged.

    ``make_receiver`` is None for a function or static method (no receiver) — the callable is used
    as-is (after unwrapping a staticmethod descriptor on the mutant side). Otherwise the callable is
    wrapped so each invocation prepends a fresh receiver. Applied identically to the original and to
    every compiled mutant, which is what keeps the two arity-symmetric."""
    fn = _unwrap_descriptor(fn)
    if make_receiver is None:
        return fn
    return ReceiverBound(fn, make_receiver)


@dataclass(frozen=True)
class ExecutionBinding:
    """Everything a call site needs to EXECUTE and RENDER a target once its binding is resolved.

    ``underlying`` is the raw function to hand ``_compile_mutant`` (for ``__globals__``) and to wrap;
    ``make_receiver`` (None for function/static) builds the receiver each call; ``call_expr`` /
    ``import_name`` render the generated test's call and import; ``refusal`` (non-None) is a NAMED
    reason the target cannot be pinned by synthesis (a property, an unsupported descriptor, or a
    constructor that needs arguments) — surfaced instead of a silent ``0/N killed``."""

    binding: TargetBinding
    plan: ReceiverPlan | None
    underlying: Any
    make_receiver: Callable[[], Any] | None
    call_expr: str
    import_name: str
    refusal: str | None


def resolve_execution(
    node: ast.AST,
    qualname: str,
    live: Any,
    factory_spec: Callable[[], Any] | None = None,
    factory_render: str | None = None,
) -> ExecutionBinding:
    """Classify ``live`` (what ``_load_original`` returned) and resolve how to call it (#25).

    ``factory_spec``/``factory_render`` come from an explicit ``--receiver-factory``. The evidence
    order for an instance receiver is in :func:`resolve_receiver_plan` (explicit factory → contained
    zero-arg ``Owner()`` → ``needs-receiver``). A classmethod's receiver is always its owner class; a
    static method / function has none. A property or unknown descriptor is refused by name."""
    binding = binding_from_node(node, qualname)
    ns = getattr(live, "__globals__", {}) or {}
    call_expr, import_name = call_expr_and_import(binding, None)

    if binding.kind is BindingKind.FUNCTION:
        return ExecutionBinding(binding, None, live, None, call_expr, import_name, None)
    if binding.kind is BindingKind.STATIC_METHOD:
        return ExecutionBinding(
            binding, None, underlying_function(live, binding), None, call_expr, import_name, None
        )
    if binding.kind is BindingKind.PROPERTY:
        return ExecutionBinding(
            binding,
            None,
            live,
            None,
            call_expr,
            import_name,
            f"needs-fixture — {binding.owner}.{binding.attribute} is a property; it has no call "
            "signature to synthesize (a property is read, not called)",
        )
    if binding.kind is BindingKind.UNSUPPORTED:
        return ExecutionBinding(
            binding,
            None,
            live,
            None,
            call_expr,
            import_name,
            f"needs-fixture — {qualname} is an unsupported descriptor; its call convention is not "
            "modelled, so no receiver is guessed",
        )

    owner_cls = ns.get(binding.owner)
    if binding.kind is BindingKind.CLASS_METHOD:
        if owner_cls is None:
            return ExecutionBinding(
                binding,
                None,
                live,
                None,
                call_expr,
                import_name,
                f"needs-receiver — could not resolve the owner class {binding.owner!r} of "
                f"{qualname} in its module",
            )
        plan = ReceiverPlan(
            lambda: owner_cls, f"{binding.owner}.{binding.attribute}", f"class:{binding.owner}"
        )
        return ExecutionBinding(
            binding, plan, underlying_function(live, binding), plan.factory, call_expr, import_name, None
        )

    # INSTANCE_METHOD — the case that needs a constructed receiver.
    plan = resolve_receiver_plan(owner_cls, binding.owner, factory_spec, factory_render)
    if plan is None:
        hint = f" (supply --receiver-factory pkg.mod:make for {binding.owner})"
        return ExecutionBinding(
            binding,
            None,
            live,
            None,
            call_expr,
            import_name,
            f"needs-receiver — {binding.owner}() could not be constructed without arguments{hint}",
        )
    inst_call, inst_import = call_expr_and_import(binding, plan)
    return ExecutionBinding(binding, plan, live, plan.factory, inst_call, inst_import, None)
