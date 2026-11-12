"""Is a computed FIELD actually READ — the question `consumption.py` asks of functions, asked of data.

`consumption.py` guards that every pinned FUNCTION has a consumer. A dataclass FIELD that production
computes and nothing reads is invisible to it: the value is produced on every run, carried through
every layer, and never reaches a decision, a page or `--json` (`capability_flags` was the motivating
case; Detective#94, EP-G2). It is the same defect one level down — "a computed signal no layer
consumes" — and it hides for the same reason: every test that builds the object passes.

    "Every computed field is read, or it goes."   (founder ruling, ENGINEERING_PASS §6 item 18)

WHAT COUNTS AS A READ, from the AST of every module under the package:

* an attribute load, ``obj.field``, outside the body of the class that declares it;
* ``getattr(obj, "field")`` / ``getattr(obj, "field", default)``, the string spelling of the same read;
* a class pattern, ``case Cls(field=...)``.

WHAT DOES NOT. A store (``obj.field = v``), a keyword in a constructor call (that is the PRODUCER), and
a read inside the declaring class's own body (a ``@property`` over the field is a derived view whose own
reader is then the thing to count). Test code is counted apart, because a field only a test reads is a
field no user ever sees: ``test_only`` is its own code.

REFLECTION AND EQUALITY (COMMUNICATING_DETERMINISM §11). A by-name reading OVERSTATES unreadness in two
ways, and neither may be a free pass: ``asdict`` / ``to_json`` emit whole objects, so a field reaches
``--json`` without any attribute being read by name, and a frozen dataclass's generated ``__eq__`` /
``__hash__`` consumes every field. Such a field needs a registry entry whose reason NAMES THE SITE as an
``asdict@module.function`` or ``eq@module.function`` token, and `reflection_sites` lets a test verify that
the named function really does call a reflective emitter (or compare). The site is checked, not trusted.

KNOWN LIMITS, stated rather than papered over:

* The read is by NAME. Two classes that declare the same field name share each other's reads, so a
  field can read as consumed on the strength of a different class's attribute of the same name. That is
  the false-CLEAN direction, the one a guard should not have; `ambiguous_names` lists the names it
  applies to so a reader can see how much of the population it touches.
* Dynamic access (``getattr(obj, name_variable)``, ``fields(obj)`` loops) is invisible. A field read
  only that way is reported unread and takes a registry entry naming the dynamic reader.

Deliberately NOT wired into any verb, like `consumption.py`: a repo-discipline instrument whose decision
lives in the package so `converge` can pin it.
"""

from __future__ import annotations

import ast
import pathlib
import re

READ = "read"
REGISTRY_STALE = "registry_stale"
EXEMPT_DECLARED = "exempt_declared"
TEST_ONLY = "test_only"
UNREAD = "unread"
REFLECTED = "reflected"

# `asdict@module.function`: the house spelling of "this site emits the whole object by reflection".
_SITE_TOKEN = re.compile(r"\b(asdict|eq)@([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)+)")

_REFLECTIVE_CALLS = frozenset({"asdict", "to_json", "astuple", "fields", "vars", "replace"})


def field_consumption_disposition(
    production_reads: int, test_reads: int, reflected_via: str, exemption_reason: str
) -> str:
    """What a dataclass field's read counts warrant (#94, pure — pinned). Named codes, because these
    are six different facts about a field with six different remedies:

      "read"             production code reads it. Nothing to answer.
      "registry_stale"   production reads it AND it carries a registry reason. The reason outlived the
                         fact it recorded and should be DELETED, as `consumption_disposition` says of
                         an exemption nobody re-checks.
      "exempt_declared"  no production read, and a reason is on record naming what consumes it
                         (a generated ``__eq__``, a dynamic reader, a research harness).
      "reflected"        no production read and no reason, but its class is reachable from a VERIFIED
                         emission root (`reflected_via` names the site: a function that calls ``asdict``
                         on the root, or a public API return type): the field reaches ``--json`` or a
                         library caller without any attribute being read by name. Not a free pass: the
                         test pins how many fields rest on this, so a new one is a deliberate edit.
      "test_only"        no production read, no reason, not reflected, but a test reads it: the
                         `state_basis` shape, where every check that could pass does and none asks
                         whether a user can see it.
      "unread"           none of the above. Computed and carried, never consumed: wire it to the page
                         or `--json` where its meaning belongs, or delete it and its producer.

    `reflected_via` is "" when no verified root reaches the field. An empty or whitespace-only reason
    is NOT an exemption: silence cannot buy silence.
    """
    if production_reads > 0:
        return REGISTRY_STALE if exemption_reason.strip() else READ
    if exemption_reason.strip():
        return EXEMPT_DECLARED
    if reflected_via.strip():
        return REFLECTED
    if test_reads > 0:
        return TEST_ONLY
    return UNREAD


def reflection_site_tokens(reason: str) -> list[tuple[str, str]]:
    """The ``(kind, site)`` pairs a registry reason names, e.g. ``[("asdict", "cli._run_receipt")]``.

    A reason with no token names no site, and the guard's test treats a reflection claim without one as
    an unverifiable assertion rather than as evidence."""
    return [(m.group(1), m.group(2)) for m in _SITE_TOKEN.finditer(reason)]


def dataclass_fields(package_dir: str) -> dict[str, str]:
    """Every field of every dataclass in `package_dir`, as ``module.Class.field -> path:line``.

    A dataclass is a class decorated ``@dataclass`` / ``@dataclass(...)`` / ``@dataclasses.dataclass``.
    A field is an annotated name in the class body, ``ClassVar`` excluded (it is not an instance field).
    Nested classes are reached with their dotted qualname."""
    out: dict[str, str] = {}
    for path, tree in _parsed(package_dir):
        for qual, node in _classes(tree, ""):
            if not _is_dataclass(node):
                continue
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and not _is_classvar(stmt.annotation)
                ):
                    out[f"{path.stem}.{qual}.{stmt.target.id}"] = f"{path}:{stmt.lineno}"
    return out


def field_read_counts(roots: tuple[str, ...], fields: dict[str, str]) -> dict[str, int]:
    """How many READS each field has under `roots` — see the module docstring for what is one.

    A read inside the body of a class named like the field's declaring class is not a read of its own
    (the file is matched by its stem, so a same-named class in another module is not), EXCEPT through
    an accessor: a read inside a non-dunder method or property ``M`` of the declaring class counts when
    ``M`` itself is read outside that class, because ``M`` is then how the field reaches a consumer."""
    observed: list[tuple[str, str, tuple[str, ...], str]] = []
    for root in roots:
        for path, tree in _parsed(root):
            observed.extend((path.stem, name, inside, method) for name, inside, method in _reads(tree))
    counts = dict.fromkeys(fields, 0)
    by_name: dict[str, list[tuple[str, str, str]]] = {}
    for key in fields:
        module, rest = key.split(".", 1)
        cls, name = rest.rsplit(".", 1)
        by_name.setdefault(name, []).append((key, module, cls))
    sites: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for stem, name, inside, _method in observed:
        sites.setdefault(name, []).append((stem, inside))
    for stem, name, inside, method in observed:
        for key, module, cls in by_name.get(name, ()):
            if stem == module and cls in inside:
                accessor = (
                    bool(method)
                    and not method.startswith("__")
                    and any(not (st == module and cls in ins) for st, ins in sites.get(method, ()))
                )
                if not accessor:
                    continue
            counts[key] += 1
    return counts


def class_graph(package_dir: str) -> dict[str, frozenset[str]]:
    """Dataclass name -> the dataclass names its field annotations mention (one edge per mention).

    ``asdict`` recurses through dataclass-typed fields, so what a root emits is exactly what its
    annotations can reach; this is that reachability, read from the AST rather than assumed."""
    names: set[str] = set()
    annotations: dict[str, list[str]] = {}
    for _path, tree in _parsed(package_dir):
        for qual, node in _classes(tree, ""):
            if _is_dataclass(node):
                simple = qual.rsplit(".", 1)[-1]
                names.add(simple)
                annotations.setdefault(simple, []).extend(
                    ast.unparse(s.annotation)
                    for s in node.body
                    if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
                )
    return {
        cls: frozenset(
            w for text in anns for w in re.findall(r"[A-Za-z_]\w*", text) if w in names and w != cls
        )
        for cls, anns in annotations.items()
    }


def reachable_classes(graph: dict[str, frozenset[str]], root: str) -> frozenset[str]:
    """`root` and every dataclass reachable from it through field annotations."""
    seen = {root}
    stack = [root]
    while stack:
        for nxt in graph.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return frozenset(seen)


def ambiguous_names(fields: dict[str, str]) -> dict[str, list[str]]:
    """Field names declared by MORE THAN ONE dataclass: a by-name read of one is a read of all."""
    owners: dict[str, list[str]] = {}
    for key in fields:
        owners.setdefault(key.rsplit(".", 1)[1], []).append(key)
    return {name: keys for name, keys in owners.items() if len(keys) > 1}


def reflection_sites(package_dir: str) -> dict[str, frozenset[str]]:
    """For every function under `package_dir`, which reflection a registry token can name there.

    Maps ``module.function`` (methods as ``module.Class.method``) to a subset of ``{"asdict", "eq"}``:
    ``asdict`` when the body calls a reflective emitter (``asdict``, ``to_json``, ``astuple``,
    ``fields``, ``vars``), ``eq`` when it compares two values with ``==`` / ``!=``. The test that holds
    the registry to its tokens reads this, so a token naming a function that does neither fails."""
    out: dict[str, frozenset[str]] = {}
    for path, tree in _parsed(package_dir):
        for qual, fn in _functions(tree, ""):
            kinds: set[str] = set()
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and _call_name(node) in _REFLECTIVE_CALLS - {"replace"}:
                    kinds.add("asdict")
                elif isinstance(node, ast.Compare) and any(
                    isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops
                ):
                    kinds.add("eq")
            out[f"{path.stem}.{qual}"] = frozenset(kinds)
    return out


# ----------------------------------------------------------------------------- gathering


def _parsed(root: str) -> list[tuple[pathlib.Path, ast.Module]]:
    """Every parseable .py under `root`, vendored Lean packages excluded (as `consumption` does)."""
    base = pathlib.Path(root)
    out: list[tuple[pathlib.Path, ast.Module]] = []
    if not base.exists():
        return out
    for path in sorted(base.rglob("*.py")):
        if ".lake" in path.parts:
            continue
        try:
            out.append((path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
    return out


def _classes(node: ast.AST, prefix: str):
    """``(qualname, ClassDef)`` for every class reachable through class bodies (not function bodies)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            qual = f"{prefix}{child.name}"
            yield qual, child
            yield from _classes(child, f"{qual}.")


def _functions(node: ast.AST, prefix: str):
    """``(qualname, FunctionDef)`` for module-level functions and methods, one level of class nesting."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield f"{prefix}{child.name}", child
        elif isinstance(child, ast.ClassDef):
            yield from _functions(child, f"{prefix}{child.name}.")


def _is_dataclass(node: ast.ClassDef) -> bool:
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", "")
        if name == "dataclass":
            return True
    return False


def _is_classvar(annotation: ast.expr) -> bool:
    text = ast.unparse(annotation)
    return text.startswith(("ClassVar", "typing.ClassVar", "'ClassVar", '"ClassVar'))


def _call_name(call: ast.Call) -> str:
    return call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")


def _reads(tree: ast.Module):
    """``(attribute_name, enclosing_class_names, enclosing_method)`` for every read in one module.

    ``enclosing_method`` is the name of the function defined directly in the innermost class body that
    contains the read, or "" outside any method."""

    def walk(node: ast.AST, inside: tuple[str, ...], method: str):
        if isinstance(node, ast.ClassDef):
            inside, method = (*inside, node.name), ""
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and inside and not method:
            method = node.name
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            yield node.attr, inside, method
        elif isinstance(node, ast.Call) and _call_name(node) == "getattr" and len(node.args) >= 2:
            key = node.args[1]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                yield key.value, inside, method
        elif isinstance(node, ast.MatchClass):
            for attr in node.kwd_attrs:
                yield attr, inside, method
        for child in ast.iter_child_nodes(node):
            yield from walk(child, inside, method)

    yield from walk(tree, (), "")
