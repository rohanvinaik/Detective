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
    "append",
    "extend",
    "insert",
    "remove",
    "pop",
    "clear",
    "update",
    "add",
    "discard",
    "sort",
    "reverse",
    "setdefault",
    "popitem",
}
_PATH_WRITE_METHODS = {
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rmdir",
    "touch",
    "rename",
    "replace",
}


# Calls that reach OUTSIDE this process. Deliberately not `_IMPURE_BUILTINS`: that set answers
# "does this function have observable side effects?", which is a different question and wrong in
# both directions here. It misses `shutil.rmtree`, `subprocess.run` and `requests.post` — all
# three read as PURE — while flagging `list.append` and `print`, which are perfectly safe to call
# with a made-up argument. Measured, on the shipped analyser.
_OS_WRITE_CALLS = frozenset(
    {
        "remove",
        "unlink",
        "rmdir",
        "removedirs",
        "rename",
        "renames",
        "replace",
        "mkdir",
        "makedirs",
        "truncate",
        "chmod",
        "chown",
        "symlink",
        "link",
        "utime",
        "system",
        "popen",
        "execv",
        "kill",
    }
)
_WORLD_MODULES = frozenset(
    {"shutil", "subprocess", "socket", "requests", "urllib", "httpx", "ftplib", "smtplib"}
)
# The modes that CREATE or TRUNCATE. `open(p)` is a read: it cannot damage anything, and banning
# it would cost coverage on every parser and loader for nothing.
_WRITE_MODES = ("w", "a", "x", "+")


@dataclass(frozen=True)
class PurityResult:
    """Whether a function is pure, and the reasons it is not."""

    is_pure: bool
    reasons: tuple[str, ...]


def world_effects(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """The ways ``func`` can affect the world OUTSIDE this process — empty if it cannot.

    This exists to answer one question: **is it safe to call this with an argument we invented?**
    Detective's equivalence search runs the target over candidate inputs, and its grids fabricate
    values — `_grid_for("str")` is `["", "a", "abc"]`. For a function that writes files, that is
    not a guess, it is damage: `_declare_pythonpath("")` resolved `pyproject.toml` against the
    CWD and edited this repository, both during classification and in the test it then emitted.

    Do NOT reach for `is_pure` here; it was measured and it is wrong both ways (see the sets
    above). Purity gates STATE mutations and corroborates golden captures — a question about
    observability. This is a question about blast radius, and the two must not be conflated.

    Local scan only — the same v1 boundary `analyze_function` documents. A helper one level down
    that calls `rmtree` is not seen. That is a real limit, and it is why this gates INPUT
    FABRICATION rather than pretending to be a safety proof: the rule it enforces is "do not
    invent a value for this", not "this function is dangerous".
    """
    visitor = _WorldEffectVisitor()
    visitor.visit(func)
    return tuple(dict.fromkeys(visitor.reasons))  # deduped, order preserved


class _WorldEffectVisitor(ast.NodeVisitor):
    """Finds calls that escape the process. Conservative: unsure reads as an effect."""

    def __init__(self) -> None:
        self.reasons: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = get_name(node.func)
        if name:
            root, method = name.split(".")[0], name.split(".")[-1]
            if name == "open" and self._opens_for_write(node):
                self.reasons.append("opens a file for writing")
            elif root == "os" and method in _OS_WRITE_CALLS:
                self.reasons.append(f"filesystem/process call os.{method}()")
            elif root in _WORLD_MODULES:
                self.reasons.append(f"calls {root}.{method}()")
        # `node.func.attr` directly, NOT via `get_name`: the receiver is frequently a Call —
        # `Path(p).write_text(...)` — which `get_name` cannot name, so it returns None and the
        # whole branch is skipped. Measured: `Path(p).write_text()` read as effect-free, which
        # is the single most common way Python code writes a file.
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in _PATH_WRITE_METHODS and not (attr == "replace" and len(node.args) != 1):
                self.reasons.append(f"filesystem write via .{attr}()")
        self.generic_visit(node)

    @staticmethod
    def _opens_for_write(node: ast.Call) -> bool:
        """Is this `open(...)` a write? A literal read-mode is the ONLY thing treated as safe.

        A mode we cannot read (a variable, an f-string) is treated as a write: guessing "probably
        a read" is how a guard becomes decorative.
        """
        mode = next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
        if mode is None and len(node.args) > 1:
            mode = node.args[1]
        if mode is None:
            return False  # `open(p)` — the default is "r"
        if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            return any(m in mode.value for m in _WRITE_MODES)
        return True  # unreadable mode — assume the worst


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
        # PARAMETERS ARE NOT LOCAL. A parameter name is an ALIAS to an object the CALLER
        # owns; mutating through it (``items.append(x)``, ``cfg[k] = v``, ``obj.attr = v``)
        # is a side effect the caller observes. Seeding ``local_names`` with the parameters
        # made ``_external()`` False for every argument, so NO argument mutation could ever
        # be a reason and ``is_pure`` returned True for all of them — measured: list append,
        # dict write, in-place sort and attribute writes all reported pure, with only
        # globals/nonlocals caught. That mislabelling is worse than a miss: ``is_pure``
        # gates STATE off and steers golden capture to the return value alone, so the one
        # behavior no assertion sees gets certified as absent.
        #
        # A param REBOUND to a local value stops being an alias, and ``visit_Assign``
        # already adds it to ``local_names`` when it is. So ``items = list(items)`` followed
        # by ``items.append(x)`` is correctly pure — which is precisely the refactor
        # (copy instead of alias) this predicate must be able to tell apart from the
        # original. Order is source order, so the rebinding is seen before the use.
        self.local_names: set[str] = set()
        if is_method:
            # ``self``/``cls`` route through ``_mutates_instance``, which carries the
            # ``__init__`` exemption. Treating them as external here would flag every
            # constructor as impure.
            self.local_names |= {"self", "cls"} & set(_param_names(func.args))
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
            # `.replace()` is overwhelmingly ``str``/``bytes`` (pure, 2+ args); only
            # ``Path.replace(target)`` — a filesystem move — takes a single positional
            # arg. Disambiguate by arity so ``s.replace(".", "_")`` is not a false write.
            if method in _PATH_WRITE_METHODS and not (method == "replace" and len(node.args) != 1):
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


# ── Environment READS that gate REACHABILITY ─────────────────────────────────────────────────
# `world_effects` answers "is it unsafe to CALL this with an invented argument?" (writes / blast
# radius). This answers the different question the residual hand-back needs: "can an `--input`
# value even REACH this branch?" A line behind `if path.exists():`, `if time.time() - t > TTL:`,
# or `os.environ.get("X")` is gated by state the caller's ARGUMENT CANNOT SET — no `model_id`
# string makes a file appear on disk, no int freezes the clock. Without this, converge asks for
# an `--input` that PROVABLY cannot close the line gap, and a driver (human or small model) loops
# forever supplying values that never land. Reporting the read lets the residual say
# "fixture / manual test, not `--input`" instead. Local scan, same v1 boundary as
# `analyze_function`: a read one helper down is not seen (documented, not a bug).
_CLOCK_CALLS = frozenset(
    {
        "time",
        "monotonic",
        "perf_counter",
        "time_ns",
        "monotonic_ns",
        "now",
        "utcnow",
        "today",
        "fromtimestamp",
    }
)
_ENV_CALLS = frozenset(
    {"getenv", "getpid", "getppid", "urandom", "uname", "getuser", "getlogin", "getcwd", "cpu_count"}
)
_FS_READ_METHODS = frozenset(
    {
        "exists",
        "is_file",
        "is_dir",
        "is_symlink",
        "stat",
        "lstat",
        "glob",
        "rglob",
        "iterdir",
        "read_text",
        "read_bytes",
        "samefile",
    }
)
_FS_READ_CALLS = frozenset(
    {
        "exists",
        "isfile",
        "isdir",
        "islink",
        "getsize",
        "getmtime",
        "getctime",
        "listdir",
        "scandir",
        "stat",
        "lstat",
    }
)
_ENTROPY_ROOTS = frozenset({"random", "secrets"})


def environment_reads(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """The ways ``func`` READS state a caller's argument cannot set — empty if it reads none.

    This exists to answer: **can an ``--input`` value reach an un-exercised branch, or is that
    branch gated by the environment?** Detective's line-gap residual hands the driver a
    ``--input "(…)"`` skeleton to reach uncovered lines. For a line behind `path.exists()`,
    `time.time()`, `os.environ[…]`, or `random.random()`, that ask is impossible: the gate reads
    the filesystem / clock / process, not the argument, so no value of the argument reaches it —
    and a driver that keeps trying makes no progress. Surfacing the read turns "author more
    `--input`" into the honest "supply a fixture or write this by hand".

    NOT ``world_effects``: that flags WRITES and is about blast radius. A pure read like
    `path.exists()` has no blast radius but still gates reachability, and the two questions have
    opposite answers here. Local scan only — an environment read one helper down is not seen.
    """
    visitor = _EnvironmentReadVisitor()
    visitor.visit(func)
    return tuple(dict.fromkeys(visitor.reasons))  # deduped, order preserved


def uncovered_env_reads(
    env_reads: tuple[str, ...], clock_supplied: bool, env_supplied: bool = False
) -> tuple[str, ...]:
    """Which of ``env_reads`` have NO explicit capability controlling them — the reads that make a
    golden capture INADMISSIBLE and must be declined rather than guessed (issue #39).

    Capturability is not purity. ``is_pure`` + no world writes says the function does not *change*
    the world; it says nothing about whether its RETURN depends on external state a caller cannot
    set. Golden synthesis calls "two back-to-back reprs match" deterministic, which admits any read
    whose stability window is longer than the sampling interval — the clock (``int(time.time())``
    is stable for a second, then not), the calendar date, the PID, the process environment. Each is
    the README's declined case, and each can end in ``✓ COMPLETE``.

    A read is COVERED only by a caller-supplied capability. The one capability today is ``--clock``,
    which freezes ``time.time()`` to a fixed value threaded into every capture — so a ``time.time()``
    read is covered when ``clock_supplied``. EVERY other read is uncovered until its fixture exists
    (#24): ``date.today`` (v1 ``--clock`` freezes ``time.time()`` only — a date golden passes today
    and fails tomorrow), ``os.getpid``, ``os.environ``, filesystem reads, entropy. Returned as the
    exact dependency reasons so the refusal names why, not merely that.
    """
    from .capabilities import clock_covers, env_covers

    # A read is covered by whichever capability controls it: --clock for the time-module clocks,
    # --env for the process environment (#48). Per-variable admissibility (was THIS var declared) is
    # decided later at capture; this class-level gate only stops declining an env read out of hand
    # when an env capability was supplied at all.
    return tuple(
        r for r in env_reads if not ((clock_supplied and clock_covers(r)) or (env_supplied and env_covers(r)))
    )


class _EnvironmentReadVisitor(ast.NodeVisitor):
    """Finds reads of clock / filesystem / process-env / entropy that gate reachability."""

    def __init__(self) -> None:
        self.reasons: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = get_name(node.func)
        if name:
            root, method = name.split(".")[0], name.split(".")[-1]
            if root in ("time", "datetime", "date") and method in _CLOCK_CALLS:
                self.reasons.append(f"reads the clock via {name}()")
            elif root == "os" and method in _ENV_CALLS:
                self.reasons.append(f"reads process/env via os.{method}()")
            elif root == "os" and method in _FS_READ_CALLS:  # os.path.exists(), os.listdir(), …
                self.reasons.append(f"reads the filesystem via {name}()")
            elif name == "open":
                self.reasons.append("reads a file via open() (the file must exist)")
            elif root in _ENTROPY_ROOTS:
                self.reasons.append(f"reads entropy via {name}()")
            elif root == "uuid" and method in ("uuid1", "uuid3", "uuid4", "uuid5"):
                self.reasons.append(f"reads entropy via {name}()")
            elif root in _WORLD_MODULES:
                self.reasons.append(f"reads the world via {root}.{method}()")
        # Path/os read methods on any receiver — `Path(p).exists()`, `p.read_text()`. Checked via
        # `node.func.attr` directly, NOT `get_name`: the receiver is often itself a Call the namer
        # cannot resolve, exactly as `_WorldEffectVisitor` documents for the write side.
        if isinstance(node.func, ast.Attribute) and node.func.attr in _FS_READ_METHODS:
            self.reasons.append(f"reads the filesystem via .{node.func.attr}()")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # `os.environ` in any access form — `os.environ["X"]`, `os.environ.get("X")` — resolves to
        # this attribute node; naming it once (deduped) covers both.
        if get_name(node) == "os.environ":
            self.reasons.append("reads process env via os.environ")
        self.generic_visit(node)
