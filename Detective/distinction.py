"""Does every consumer of a pinned decision distinguish all of its codes — the question §3.2 left open.

`docs/theory/COMMUNICATING_DETERMINISM.md` §3.2 names two questions that decide whether the map from
epistemic state to emitted sign is injective, and calls both decidable over the reference graph. The
first, whether every decision is consumed at all, is `consumption.py`. This is the second, §9's
invariant 3:

    Every consumer distinguishes all of a decision's codes, or names the ones it deliberately
    collapses and why.

It was found by hand twice before this existed. `certify._TERMINAL_STANDINGS` admitted three of the
five codes `certificate_standing` produces and let the other two fall through into codes meaning
absence; §MI was the other. A failure of this kind produces green suites by construction, because the
tests assert the message that is emitted and not the distinction that was lost. No test goes red until
something asks the question.

WHAT A SITE IS. A call, in the package, of a declared decision (`consumption.declared_decisions`) whose
CODE SET is closed: every `return` is a string literal or a string constant. A decision that returns
anything else is outside the population, left out rather than guessed at. One site is one decision
inside one function (the innermost function containing the call).

WHAT "DISTINGUISHES" MEANS HERE, read from the AST of that function:

* compared: `v == "a"`, `v != "a"`, `v in ("a", "b")`, `v in _A_CONSTANT`, `match v: case "a"`, or a
  string-keyed table indexed by it (`_TABLE[v]`, `_TABLE.get(v, ...)`), where `v` is the call itself, a
  name bound from it, or a value-preserving alias of it (`x = v if c else "b"`, `x = a or v`);
* the fall-through: an `else` that stands for exactly ONE remaining code distinguishes it;
* forwarded: the value itself flows on intact (returned, passed as an argument, stored into an
  attribute or subscript, packed into a container, rendered in an f-string). The distinction is then
  read downstream. This guard does not follow it, and it says `forwards` rather than calling the site
  either clean or collapsing.

KNOWN LIMITS, stated rather than papered over:

* A CALL-SITE RESTRICTION is invisible to it. A site that passes constants, or that runs after an early
  return has already taken some codes, may never receive the codes it does not name. The registry entry
  for such a site says which codes cannot arise there and why, which a reader can check.
* A RE-DERIVATION is invisible to it. A consumer that reads the raw facts again (`if not x:`) instead of
  the code distinguishes by a second reading, which §9's invariant 8 calls "drift with a delay fuse".
  Those sites read as collapses here, and the registry names them as what they are.
* Dynamic dispatch and serialization by reflection defeat the AST, as they defeat the reference graph.

The failure direction is a false FINDING, never a false clean, with one exception taken at its word:
a forwarded value is reported as `forwards`, never as distinguishing.

Deliberately NOT wired into any verb, like `consumption.py`: a repo-discipline instrument whose
decision lives in the package so `converge` can pin it.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass, field

from .consumption import declared_decisions

PHANTOM_CODE = "phantom_code"
COLLAPSE_DECLARED = "collapse_declared"
COLLAPSE_STALE = "collapse_stale"
COLLAPSES = "collapses"
FORWARDS = "forwards"
DISTINGUISHES_ALL = "distinguishes_all"


def distinction_disposition(
    codes: list[str],
    distinguished: list[str],
    forwards: bool,
    collapse_reason: str,
) -> str:
    """How one consumer reads one decision's codes (§9 invariant 3, pure — pinned).

    Named codes, because these are six different facts about a call site with six different remedies:

      "phantom_code"       the site compares against a string the decision can never return. The
                           branch can never fire. That is drift (a code renamed at the decision and
                           not at the consumer), and no recorded reason excuses it, so it outranks
                           everything.
      "collapse_declared"  two or more codes share the site's fall-through, and a reason is on record
                           saying why. The invariant's "or names the ones it deliberately collapses
                           and why".
      "collapse_stale"     a reason is on record, but the site no longer collapses. The entry outlived
                           its reason and should be DELETED. A registry nobody re-checks becomes the
                           hiding place the reason requirement exists to prevent.
      "collapses"          two or more codes share the fall-through and nothing says why. THE finding:
                           states the decision keeps apart reach this reader as one.
      "forwards"           two or more codes are not compared here, but the value itself flows on.
                           The distinction is read downstream, which this guard does not follow.
      "distinguishes_all"  every code is compared, except at most one left to the fall-through, and
                           a fall-through that stands for one code distinguishes it.

    An empty or whitespace-only reason is not a reason, the same rule `consumption_disposition`
    applies: silence cannot buy silence.
    """
    if any(code not in codes for code in distinguished):
        return PHANTOM_CODE
    merged = [code for code in codes if code not in distinguished]
    collapsing = len(merged) >= 2 and not forwards
    if collapse_reason.strip():
        return COLLAPSE_DECLARED if collapsing else COLLAPSE_STALE
    if collapsing:
        return COLLAPSES
    return FORWARDS if len(merged) >= 2 else DISTINGUISHES_ALL


@dataclass(frozen=True)
class ConsumerRead:
    """One site: one closed-code decision, called inside one function, as the AST reads it."""

    decision: str  # "module.function", the key `consumption.declared_decisions` uses
    consumer: str  # "module.outer.inner", the innermost function containing the call
    location: str  # "path:line" of the site's first call
    codes: tuple[str, ...]
    distinguished: tuple[str, ...]  # every literal compared; one the decision cannot return stays in
    forwards: bool

    @property
    def key(self) -> str:
        """The registry key: `decision @ consumer`."""
        return f"{self.decision} @ {self.consumer}"


def consumer_reads(package_dir: str) -> list[ConsumerRead]:
    """Every site in `package_dir` whose decision has a closed code set, sorted by key.

    One AST pass per module. String constants, string containers and string-keyed tables are
    resolved through a module's own assignments and its `from x import NAME` / `import x as a`
    bindings to sibling modules, so `v != HARVEST` and `v in validity.CUT_REASONS` read as the
    literals they are."""
    modules = _parse_package(package_dir)
    vocab = _vocabularies(modules)
    closed = _closed_decisions(package_dir, modules, vocab)
    reads: list[ConsumerRead] = []
    for name, mod in modules.items():
        for qual, fn, calls_by_decision in _sites(mod.tree, mod.stem, closed):
            for decision_name, calls in calls_by_decision.items():
                decision_key, codes = closed[decision_name]
                site = _Site(fn, calls)
                distinguished = site.distinguished(codes, vocab[name])
                reads.append(
                    ConsumerRead(
                        decision=decision_key,
                        consumer=qual,
                        location=f"{mod.path}:{calls[0].lineno}",
                        codes=tuple(sorted(codes)),
                        distinguished=tuple(sorted(distinguished)),
                        forwards=site.forwards(vocab[name]),
                    )
                )
    return sorted(reads, key=lambda r: (r.key, r.location))


def closed_decision_count(package_dir: str) -> tuple[int, int]:
    """(decisions with a closed code set of two or more, declared decisions in all). The population
    this guard covers, and the one it was drawn from — so a shrinking population is visible."""
    modules = _parse_package(package_dir)
    closed = _closed_decisions(package_dir, modules, _vocabularies(modules))
    return len(closed), len(declared_decisions(package_dir))


# ---------------------------------------------------------------- the gathering layer (impure)


@dataclass(frozen=True)
class _Module:
    path: pathlib.Path
    stem: str
    tree: ast.Module


def _parse_package(package_dir: str) -> dict[str, _Module]:
    """Every parseable module under `package_dir`, keyed by its dotted name. A file that will not
    parse contributes nothing rather than failing the sweep, as in `consumption`."""
    root = pathlib.Path(package_dir)
    out: dict[str, _Module] = {}
    for path in sorted(root.rglob("*.py")):
        if ".lake" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        parts = [root.name, *path.relative_to(root).with_suffix("").parts]
        if parts[-1] == "__init__":
            parts.pop()
        out[".".join(parts)] = _Module(path, path.stem, tree)
    return out


def _vocabularies(modules: dict[str, _Module]) -> dict[str, _Vocabulary]:
    """Each module's vocabulary: its own names plus the names it imports from a sibling. Imports
    resolve against the siblings' OWN names only, so the result does not depend on the order the
    modules are visited in (a name re-exported through a third module is not followed)."""
    own = {name: _Vocabulary.own(mod.tree) for name, mod in modules.items()}
    return {name: own[name].with_imports(mod.tree, name, own) for name, mod in modules.items()}


@dataclass(frozen=True)
class _Vocabulary:
    """The string constants, string collections and string-keyed tables a module can name."""

    strings: dict[str, str] = field(default_factory=dict)
    collections: dict[str, frozenset[str]] = field(default_factory=dict)
    tables: dict[str, frozenset[str]] = field(default_factory=dict)
    modules: dict[str, _Vocabulary] = field(default_factory=dict)  # `import x as a` → a's vocabulary

    @staticmethod
    def own(tree: ast.Module) -> _Vocabulary:
        strings: dict[str, str] = {}
        pending: list[tuple[str, ast.expr]] = []
        for node in tree.body:
            for target, value in _simple_assignments(node):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    strings[target] = value.value
                else:
                    pending.append((target, value))
        vocab = _Vocabulary(strings=strings)
        for target, value in pending:
            vocab.collect(target, value)
        return vocab

    def collect(self, target: str, value: ast.expr) -> None:
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.args:
            if value.func.id in ("frozenset", "set", "tuple"):
                value = value.args[0]
        if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            members = [self.literal(e) for e in value.elts]
            if members and all(m is not None for m in members):
                self.collections[target] = frozenset().union(*(m for m in members if m is not None))
        elif isinstance(value, ast.Dict) and value.keys and all(k is not None for k in value.keys):
            keys = [self.literal(k) for k in value.keys if k is not None]
            if all(k is not None for k in keys):
                self.tables[target] = frozenset().union(*(k for k in keys if k is not None))

    def with_imports(self, tree: ast.Module, dotted: str, known: dict[str, _Vocabulary]) -> _Vocabulary:
        """Own names plus every name this module imports from a sibling (anywhere in the file: the
        house style imports inside functions to break cycles)."""
        strings, colls, tables, modules = {}, {}, {}, {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            base = _absolute_module(dotted, node.level, node.module)
            for alias in node.names:
                bound = alias.asname or alias.name
                source = known.get(base)
                if source is not None and alias.name in source.strings:
                    strings[bound] = source.strings[alias.name]
                elif source is not None and alias.name in source.collections:
                    colls[bound] = source.collections[alias.name]
                elif source is not None and alias.name in source.tables:
                    tables[bound] = source.tables[alias.name]
                elif f"{base}.{alias.name}" in known:
                    modules[bound] = known[f"{base}.{alias.name}"]
        return _Vocabulary(
            strings={**strings, **self.strings},
            collections={**colls, **self.collections},
            tables={**tables, **self.tables},
            modules=modules,
        )

    def literal(self, node: ast.expr | None) -> frozenset[str] | None:
        """The string(s) an expression can evaluate to, if it is a literal, a constant, or a
        conditional between them. None for anything else."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return frozenset({node.value})
        if isinstance(node, ast.Name) and node.id in self.strings:
            return frozenset({self.strings[node.id]})
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id)
            if module is not None and node.attr in module.strings:
                return frozenset({module.strings[node.attr]})
        if isinstance(node, ast.IfExp):
            body, orelse = self.literal(node.body), self.literal(node.orelse)
            return body | orelse if body is not None and orelse is not None else None
        return None

    def members(self, node: ast.expr) -> tuple[frozenset[str], bool] | None:
        """The strings an `in` operand holds, and whether they were written AT the site (a local
        literal, where a string the decision cannot return is drift) or are a shared vocabulary
        constant (where it is simply a wider set)."""
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            out: frozenset[str] = frozenset()
            for element in node.elts:
                out |= self.literal(element) or frozenset()
            return out, True
        named = self._named(node)
        if named is not None:
            return named, False
        return None

    def table(self, node: ast.expr) -> frozenset[str] | None:
        if isinstance(node, ast.Name):
            return self.tables.get(node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id)
            return module.tables.get(node.attr) if module is not None else None
        return None

    def _named(self, node: ast.expr) -> frozenset[str] | None:
        if isinstance(node, ast.Name):
            return self.collections.get(node.id) or self.tables.get(node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id)
            if module is not None:
                return module.collections.get(node.attr) or module.tables.get(node.attr)
        return None


def _simple_assignments(node: ast.stmt) -> list[tuple[str, ast.expr]]:
    """`NAME = value`, `NAME: T = value`, and the pairwise `A, B = "a", "b"` of a module's top level."""
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return [(node.target.id, node.value)]
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return []
    target, value = node.targets[0], node.value
    if isinstance(target, ast.Name):
        return [(target.id, value)]
    if isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple) and len(target.elts) == len(value.elts):
        return [(t.id, v) for t, v in zip(target.elts, value.elts, strict=True) if isinstance(t, ast.Name)]
    return []


def _absolute_module(importer: str, level: int, module: str | None) -> str:
    """`from .x import y` inside `P.m` is `P.x`; `from ..x import y` inside `P.Q.m` is `P.x`."""
    if level == 0:
        return module or ""
    base = importer.split(".")[:-level]
    return ".".join([*base, module] if module else base)


def _closed_decisions(
    package_dir: str, modules: dict[str, _Module], vocab: dict[str, _Vocabulary]
) -> dict[str, tuple[str, frozenset[str]]]:
    """Bare function name → (`module.function` key, its code set), for each declared decision whose
    every return is a known string and which has at least two codes."""
    by_path = {str(mod.path): name for name, mod in modules.items()}
    out: dict[str, tuple[str, frozenset[str]]] = {}
    for key, where in declared_decisions(package_dir).items():
        dotted = by_path.get(where.rsplit(":", 1)[0])
        if dotted is None:
            continue
        function = key.split(".", 1)[1]
        node = next(
            (n for n in modules[dotted].tree.body if isinstance(n, ast.FunctionDef) and n.name == function),
            None,
        )
        if node is None:
            continue
        codes = _code_set(node, vocab[dotted])
        if codes is not None and len(codes) >= 2:
            out[function] = (key, codes)
    return out


def _code_set(fn: ast.FunctionDef, vocab: _Vocabulary) -> frozenset[str] | None:
    codes: frozenset[str] = frozenset()
    for node in _walk_own(fn):
        if isinstance(node, ast.Return):
            returned = vocab.literal(node.value)
            if returned is None:
                return None
            codes |= returned
    return codes


def _walk_own(fn: ast.AST):
    """`ast.walk` that does not descend into nested function definitions or lambdas."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _sites(tree: ast.Module, stem: str, closed: dict[str, tuple[str, frozenset[str]]]):
    """(consumer qualname, function node, {decision name: its calls}) for every function that calls
    a closed decision directly (not through a nested function)."""
    found = []
    stack: list[tuple[ast.AST, list[str]]] = [(tree, [stem])]
    while stack:
        node, path = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = [*path, child.name]
                calls: dict[str, list[ast.Call]] = {}
                for inner in _walk_own(child):
                    if not isinstance(inner, ast.Call):
                        continue
                    name = _callee(inner)
                    if name in closed and name != child.name:
                        calls.setdefault(name, []).append(inner)
                if calls:
                    found.append((".".join(qual), child, calls))
                stack.append((child, qual))
            elif isinstance(child, ast.ClassDef):
                stack.append((child, [*path, child.name]))
            else:
                stack.append((child, path))
    return found


def _callee(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


class _Site:
    """What one function does with one decision's result."""

    def __init__(self, fn: ast.AST, calls: list[ast.Call]):
        self._fn = fn
        self._calls = {id(c) for c in calls}
        self._direct: set[str] = set()
        self._alias: set[str] = set()
        self._bind()

    def _bind(self) -> None:
        """Names that hold the code, to a fixpoint. DIRECT: every assignment to the name is the call
        or another direct name, so the name holds a code and nothing else. ALIAS: some assignment
        carries the code (`x = code if c else "other"`, `x = a or code`), so it may hold other values."""
        assigned: dict[str, list[ast.expr]] = {}
        for node in ast.walk(self._fn):
            targets, value = _assignment_targets(node)
            if value is None:
                continue
            for name in targets:
                assigned.setdefault(name, []).append(value)
        grew = True
        while grew:
            grew = False
            for name, values in assigned.items():
                if name in self._direct:
                    continue
                if all(self.is_direct(v) for v in values):
                    self._direct.add(name)
                    self._alias.discard(name)
                    grew = True
                elif name not in self._alias and any(self.carries(v) for v in values):
                    self._alias.add(name)
                    grew = True

    def is_direct(self, node: ast.AST) -> bool:
        """The call itself, or a name that holds its result and nothing else."""
        if id(node) in self._calls:
            return True
        return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in self._direct

    def is_ref(self, node: ast.AST) -> bool:
        """The call, or any name bound to its result (direct or alias)."""
        if self.is_direct(node):
            return True
        return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in self._alias

    def carries(self, node: ast.AST) -> bool:
        """The expression evaluates to the code itself on some path (value-preserving)."""
        if self.is_ref(node):
            return True
        if isinstance(node, ast.IfExp):
            return self.carries(node.body) or self.carries(node.orelse)
        if isinstance(node, ast.BoolOp):
            return any(self.carries(v) for v in node.values)
        return False

    def flows(self, node: ast.AST) -> bool:
        """The code reaches this expression's value, possibly packed or rendered."""
        if self.carries(node):
            return True
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return any(self.flows(e) for e in node.elts)
        if isinstance(node, ast.Starred):
            return self.flows(node.value)
        if isinstance(node, ast.Dict):
            return any(v is not None and self.flows(v) for v in node.values)
        if isinstance(node, ast.JoinedStr):
            return any(self.flows(v) for v in node.values)
        if isinstance(node, ast.FormattedValue):
            return self.flows(node.value)
        return False

    def distinguished(self, codes: frozenset[str], vocab: _Vocabulary) -> set[str]:
        """Every literal the site compares the code against. Through a DIRECT reference a literal the
        decision cannot return is kept, so the disposition can call it a phantom. Through an alias
        (which may also hold other values), or against a shared table, only the decision's own codes
        count: a wider vocabulary is not drift."""
        seen: set[str] = set()
        for node in ast.walk(self._fn):
            if isinstance(node, ast.Compare):
                seen |= self._compared(node, codes, vocab)
            elif isinstance(node, ast.Match) and self.carries(node.subject):
                for case in node.cases:
                    named = _pattern_literals(case.pattern, vocab)
                    seen |= named if self.is_direct(node.subject) else named & codes
            elif isinstance(node, ast.Subscript) and self.carries(node.slice):
                seen |= (vocab.table(node.value) or frozenset()) & codes
            elif isinstance(node, ast.Call) and node.args and self.carries(node.args[0]):
                seen |= (_table_get_keys(node, vocab) or frozenset()) & codes
        return seen

    def _compared(self, node: ast.Compare, codes: frozenset[str], vocab: _Vocabulary) -> set[str]:
        seen: set[str] = set()
        operands = [node.left, *node.comparators]
        for i, op in enumerate(node.ops):
            left, right = operands[i], operands[i + 1]
            for subject, other in ((left, right), (right, left)):
                if not self.carries(subject):
                    continue
                direct = self.is_direct(subject)
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    literal = vocab.literal(other)
                    if literal is not None:
                        seen |= literal if direct else literal & codes
                elif isinstance(op, (ast.In, ast.NotIn)) and subject is left:
                    held = vocab.members(other)
                    if held is not None:
                        members, local = held
                        seen |= members if direct and local else members & codes
        return seen

    def forwards(self, vocab: _Vocabulary) -> bool:
        """Does the code itself flow on from anywhere in the function."""
        return any(self._forwards_at(node, vocab) for node in ast.walk(self._fn))

    def _forwards_at(self, node: ast.AST, vocab: _Vocabulary) -> bool:
        if isinstance(node, ast.Call):
            if id(node) in self._calls or _table_get_keys(node, vocab) is not None:
                return False
            if isinstance(node.func, ast.Name) and node.func.id == "bool":
                return False  # truthiness is a collapse, never a hand-off
            return any(self.flows(a) for a in [*node.args, *(k.value for k in node.keywords)])
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            return node.value is not None and self.flows(node.value)
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            # a lookup keyed by the code in a table this reading cannot see the keys of
            return self.carries(node.slice) and vocab.table(node.value) is None
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and node.value is not None
            and self.flows(node.value)
        ):
            stored = node.targets if isinstance(node, ast.Assign) else [node.target]
            # stored somewhere that outlives the function, or packed/rendered into a new value
            return any(isinstance(t, (ast.Attribute, ast.Subscript)) for t in stored) or not self.carries(
                node.value
            )
        return False


def _assignment_targets(node: ast.AST) -> tuple[list[str], ast.expr | None]:
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)], node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id], node.value
    if isinstance(node, ast.NamedExpr):
        return [node.target.id], node.value
    return [], None


def _table_get_keys(node: ast.Call, vocab: _Vocabulary) -> frozenset[str] | None:
    """The keys of `TABLE` when the call is `TABLE.get(key, ...)` on a string-keyed table."""
    if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
        return vocab.table(node.func.value)
    return None


def _pattern_literals(pattern: ast.pattern, vocab: _Vocabulary) -> frozenset[str]:
    if isinstance(pattern, ast.MatchValue):
        return vocab.literal(pattern.value) or frozenset()
    if isinstance(pattern, ast.MatchOr):
        out: frozenset[str] = frozenset()
        for option in pattern.patterns:
            out |= _pattern_literals(option, vocab)
        return out
    return frozenset()
