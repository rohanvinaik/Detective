"""Manual line-unreachability flags — the human oracle for the LINE ledger (issue #9).

``flag`` answers the undecidable question on the MUTATION ledger (is this survivor
equivalent?); this store answers its twin on the LINE ledger: is this uncovered
statement genuinely unreachable (a defensive branch the preceding computation makes
impossible)? Without it a function can be mutation-complete forever short of line
completeness, with no truthful way to finish.

The two ledgers stay orthogonal by construction: a line flag participates ONLY in
line-residual accounting. It kills no mutant, changes no behavioral verdict, and
never gates decomposition — the proof gate reads mutation-completeness alone.

Identity is the statement's NORMALIZED AST (position-free), scoped by function and
by ordinal among identical statements, so:

* editing the statement (or the code shifting it into a different shape) orphans the
  record instead of silently mis-applying it;
* two identical statements in different functions never alias;
* execution CONTRADICTS a flag rather than coexisting with it — a covered line's
  flag is surfaced as overridden by proof, never honored.

USER DATA: manual judgments, not regeneratable analysis. ``purge`` must never
delete this store.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import asdict, dataclass

_REL_PATH = os.path.join(".detective", "line_flags.json")


@dataclass(frozen=True)
class LineFlag:
    """A manual assertion that one statement of one function is unreachable."""

    func_key: str
    stmt_hash: str  # normalized-AST identity (see :func:`stmt_identity`)
    line: int  # where it sat when flagged — display only, never identity
    source: str  # the statement's source at flag time — display + honesty in reports
    note: str = ""


def stmt_identity(func_key: str, stmt: ast.stmt, ordinal: int = 0, context: tuple[str, ...] = ()) -> str:
    """Position-free identity for one statement of one function. ``ast.dump`` without
    attributes drops line/col, so pure movement (a reflow, an added line above) keeps
    the flag alive while ANY edit to the statement itself changes the dump and orphans
    it. ``ordinal`` distinguishes textually identical statements within one function
    (the n-th ``total = 0``); ``func_key`` keeps identical statements in different
    functions from ever aliasing.

    ``context`` is the CONTROL CONTEXT — the headers of every enclosing control
    statement. An unreachability judgment is a claim about the conditions that guard
    the statement, so editing ``if x < 0`` to ``if x < 100`` must orphan a flag on its
    body even though the body itself is untouched; hashing only the statement let the
    stale flag keep closing a residual over newly reachable code.
    """
    payload = f"{func_key}::{ordinal}::{'|'.join(context)}::{ast.dump(stmt)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _control_header(node: ast.stmt) -> str:
    """The reachability-deciding header of one control statement, position-free."""
    if isinstance(node, (ast.If, ast.While)):
        return ast.dump(node.test)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return f"{ast.dump(node.target)}|{ast.dump(node.iter)}"
    if isinstance(node, ast.Match):
        return ast.dump(node.subject)
    if isinstance(node, ast.Try) or (hasattr(ast, "TryStar") and isinstance(node, ast.TryStar)):
        return "try:" + "|".join(ast.dump(h.type) if h.type is not None else "except" for h in node.handlers)
    return ""


def control_context(func_node: ast.AST, stmt: ast.stmt) -> tuple[str, ...]:
    """Headers of every control statement enclosing ``stmt``, outermost first —
    the conditions that decide whether it can run at all."""

    def descend(node: ast.AST, acc: tuple[str, ...]) -> tuple[str, ...] | None:
        for child in ast.iter_child_nodes(node):
            if child is stmt:
                return acc
            if not any(n is stmt for n in ast.walk(child)):
                continue
            header = _control_header(child) if isinstance(child, ast.stmt) else ""
            return descend(child, acc + ((header,) if header else ()))
        return None

    return descend(func_node, ()) or ()


def resolve_statement(func_node: ast.AST, line: int) -> tuple[ast.stmt, int, tuple[str, ...]] | None:
    """The innermost statement of ``func_node`` whose own header line is ``line``
    (falling back to the innermost statement whose span contains it), plus its
    ordinal among statements with an identical normalized dump and its control
    context. None when the line is not inside this function."""
    exact: ast.stmt | None = None
    containing: ast.stmt | None = None
    for node in ast.walk(func_node):
        if not isinstance(node, ast.stmt) or node is func_node:
            continue
        end = node.end_lineno or node.lineno
        if node.lineno == line:
            exact = node if exact is None else exact
        elif node.lineno <= line <= end:
            # prefer the tightest span, walk order already goes outside-in
            containing = node
    stmt = exact or containing
    if stmt is None:
        return None
    dump = ast.dump(stmt)
    ordinal = 0
    for node in ast.walk(func_node):
        if isinstance(node, ast.stmt) and node is not stmt and ast.dump(node) == dump:
            if node.lineno < stmt.lineno:
                ordinal += 1
    return stmt, ordinal, control_context(func_node, stmt)


def _store_path(project_root: str) -> str:
    return os.path.join(project_root, _REL_PATH)


def load_line_flags(project_root: str) -> dict[str, LineFlag]:
    """Every persisted line flag, keyed by :func:`stmt_identity`. Empty (never an
    error) when the store is absent or unreadable — a missing oracle is no oracle."""
    try:
        with open(_store_path(project_root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    flags: dict[str, LineFlag] = {}
    for key, value in raw.items():
        try:
            flags[key] = LineFlag(**value)
        except (TypeError, ValueError):
            continue  # a malformed entry is skipped, never fatal
    return flags


def save_line_flags(project_root: str, flags: dict[str, LineFlag]) -> None:
    from .atomic_store import atomic_write_text

    path = _store_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Atomic replace (#63): a line-unreachability flag is an irreducible human judgement — a mid-write
    # crash must leave the prior store intact, never a half-written file the next load reads as empty.
    atomic_write_text(path, json.dumps({key: asdict(flag) for key, flag in flags.items()}, indent=2))


def add_line_flag(
    project_root: str, func_key: str, func_node: ast.AST, line: int, note: str = ""
) -> LineFlag | None:
    """Record (or replace) a manual unreachability flag for the statement at ``line``.
    None when the line resolves to no statement of this function."""
    resolved = resolve_statement(func_node, line)
    if resolved is None:
        return None
    stmt, ordinal, context = resolved
    flag = LineFlag(
        func_key=func_key,
        stmt_hash=stmt_identity(func_key, stmt, ordinal, context),
        line=line,
        source=ast.unparse(stmt).splitlines()[0],
        note=note,
    )
    flags = load_line_flags(project_root)
    flags[flag.stmt_hash] = flag
    save_line_flags(project_root, flags)
    return flag


def _current_identities(func_key: str, func_node: ast.AST) -> set[str]:
    """The identity of every statement the function CURRENTLY contains — the set a
    stored flag must hit to still be meaningful."""
    idents: set[str] = set()
    seen: dict[str, int] = {}
    for node in ast.walk(func_node):
        if not isinstance(node, ast.stmt) or node is func_node:
            continue
        dump = ast.dump(node)
        ordinal = seen.get(dump, 0)
        seen[dump] = ordinal + 1
        idents.add(stmt_identity(func_key, node, ordinal, control_context(func_node, node)))
    return idents


def flag_statuses(project_root: str, func_key: str, func_node: ast.AST) -> list[tuple[LineFlag, str]]:
    """Every flag recorded for ``func_key`` with its disposition: ``current`` (its
    statement still exists under the same guards) or ``orphaned`` (the statement or a
    controlling condition changed — the record no longer applies). The inspection
    surface issue #9's second round asked for: durable human data must be listable
    before anyone is asked to trust or clean it."""
    idents = _current_identities(func_key, func_node)
    return [
        (flag, "current" if flag.stmt_hash in idents else "orphaned")
        for flag in load_line_flags(project_root).values()
        if flag.func_key == func_key
    ]


def remove_line_flag(project_root: str, func_key: str, func_node: ast.AST, line: int) -> LineFlag | None:
    """Delete one exact flag: matched by current statement identity at ``line`` when
    it resolves, else by the line as recorded (so an orphaned record whose statement
    moved or changed is still removable by the number the listing shows)."""
    flags = load_line_flags(project_root)
    key: str | None = None
    resolved = resolve_statement(func_node, line)
    if resolved is not None:
        stmt, ordinal, context = resolved
        candidate = stmt_identity(func_key, stmt, ordinal, context)
        if candidate in flags and flags[candidate].func_key == func_key:
            key = candidate
    if key is None:
        key = next((k for k, f in flags.items() if f.func_key == func_key and f.line == line), None)
    if key is None:
        return None
    removed = flags.pop(key)
    save_line_flags(project_root, flags)
    return removed


def clean_orphaned_flags(project_root: str, func_key: str, func_node: ast.AST) -> list[LineFlag]:
    """Delete only the CONFIRMED-orphaned records for one function and return them.
    Current records are never touched — cleanup is for identities the code has
    already walked away from, not a bulk reset."""
    idents = _current_identities(func_key, func_node)
    flags = load_line_flags(project_root)
    removed = [
        flags.pop(k)
        for k in [k for k, f in flags.items() if f.func_key == func_key and f.stmt_hash not in idents]
    ]
    if removed:
        save_line_flags(project_root, flags)
    return removed


def classify_missing_lines(
    project_root: str,
    func_key: str,
    func_node: ast.AST,
    missing: list[int],
    covered: set[int] | None = None,
) -> tuple[list[int], list[int], list[LineFlag]]:
    """Split the line residual by the oracle: ``(still_missing, manually_unreachable,
    contradicted)``.

    A missing line whose CURRENT statement identity matches a flag is manually
    unreachable — closed on the line ledger only, and reported as such rather than
    silently as covered. A flag whose statement was EXECUTED (its line in
    ``covered``) is contradicted: execution is proof of reachability and proof
    outranks an opinion, so the flag is surfaced and ignored, mirroring how a real
    witness overrides an equivalence flag."""
    flags = load_line_flags(project_root)
    if not flags:
        return list(missing), [], []
    still: list[int] = []
    manual: list[int] = []
    for line in missing:
        resolved = resolve_statement(func_node, line)
        if resolved is None:
            still.append(line)
            continue
        stmt, ordinal, context = resolved
        if stmt_identity(func_key, stmt, ordinal, context) in flags:
            manual.append(line)
        else:
            still.append(line)
    contradicted: list[LineFlag] = []
    for cov in sorted(covered or ()):
        resolved = resolve_statement(func_node, cov)
        if resolved is None:
            continue
        stmt, ordinal, context = resolved
        flag = flags.get(stmt_identity(func_key, stmt, ordinal, context))
        if flag is not None and flag.func_key == func_key:
            contradicted.append(flag)
    return still, manual, contradicted
