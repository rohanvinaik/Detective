"""Is a pinned pure decision actually CONSUMED — the question no index could have listed.

Found 2026-09-09. `ledger.state_basis` was ✓ COMPLETE 11/11, exported, documented and tested, and
had ZERO production callers, so the founder's ruling it implemented could never fire. Then
`converge.reproducibility_verdict`, whose intent guard pinned a property against a function
production never called. Neither was in any open-items index, and neither index was wrong: an index
lists what someone thought to file, and nobody had posed the question.

    A pin proves the decision does what it says. It says NOTHING about whether anything asks it.

That gap is decidable — it is a property of the reference graph — which is what separates this from
the kind of mechanical gate that fails. It does not judge whether a decision is meaningful, correct
or well named. It answers one question with a countable answer, and hands everything else to a
person.

WHY AN EXEMPTION MUST CARRY A REASON (founder ruling 2026-09-09: *"the solution isn't to hide from
the dark, it's to throw some light on it"*). A bare allow-list is a place to hide — a name added to
silence a finding looks identical to a name that belongs there. So the disposition takes the REASON,
not a boolean, and an empty reason is not an exemption. A registry entry has to say what DOES consume
the decision, which makes it auditable by reading rather than by trusting.

KNOWN LIMIT, stated rather than papered over. `call_counts` reads the AST, so a call reached by
dynamic dispatch — ``getattr(mod, name)()``, a registry, a table of callables — is invisible to it
and reports as unconsumed. That is the same blind spot the reference graph has, and the remedy is
the same: a declared exemption naming the dynamic consumer. The failure direction is a false
FINDING, never a false clean, which is the right way round for a guard.

This module is deliberately NOT wired into any verb. It is a repo-discipline instrument, and it
lives here rather than beside its test because the decision it rests on must be somewhere `converge`
can pin.
"""

from __future__ import annotations

import ast
import pathlib
import re

# The house declaration tag: the two words, in order, close together. `\bpure\b` is what keeps
# "impure" out — see `declares_pinned_decision` for why that is not a hypothetical. The 40-character
# window spans every real spelling in this codebase, including the ones wrapped across a line.
_PINNED_TAG = re.compile(r"\bpure\b.{0,40}?\bpinned\b", re.IGNORECASE | re.DOTALL)


def consumption_disposition(
    production_callers: int,
    other_callers: int,
    exemption_reason: str,
) -> str:
    """What a declared pure decision's call counts warrant (pure — pinned).

    Named codes, because these are five different facts about a symbol and five different remedies,
    and a `bool` "is it fine" would collapse the two that matter most into the three that do not:

      "consumed"           production calls it. Nothing to answer.
      "exemption_stale"    production calls it AND it carries an exemption. The exemption outlived
                           its reason and should be DELETED — a registry that accumulates entries
                           nobody re-checks becomes the hiding place the reason requirement exists
                           to prevent. Reported, not tolerated.
      "exempt_declared"    no production caller, and a reason is on record naming what does consume
                           it (a `dev/` research harness, a dynamic dispatch the AST cannot see).
      "pinned_unconsumed"  no production caller, no reason, but something else calls it — which in
                           practice means its own tests. THE `state_basis` shape: every check that
                           could pass does, and none of them covers whether it is wired.
      "unreferenced"       nothing calls it anywhere. Either dead, or built ahead of a consumer that
                           never arrived. Distinct from `pinned_unconsumed` because "someone pinned
                           it and forgot to wire it" and "nothing anywhere touches it" are different
                           stories about how it got here, and they are fixed differently.

    An empty or whitespace-only reason is NOT an exemption. That is the whole point of taking the
    reason rather than a flag: silence cannot buy silence.
    """
    if production_callers > 0:
        return "exemption_stale" if exemption_reason.strip() else "consumed"
    if exemption_reason.strip():
        return "exempt_declared"
    if other_callers > 0:
        return "pinned_unconsumed"
    return "unreferenced"


def declares_pinned_decision(docstring: str) -> bool:
    """Does this docstring declare its function a pinned pure decision (pure — pinned).

    The house tag is a parenthetical carrying both words — ``(pure — pinned)``, ``(#NN, pure —
    pinned)``, ``(F2 — pure, pinned)``, sometimes wrapped across a line. The spellings vary across
    ~157 sites and normalising them would be a migration with no behavioural payoff, so this matches
    the SHAPE rather than a fixed string: the two words, in order, close together.

    "Close together" is doing real work, and so is the word boundary. A bare ``"pure" in text`` — the
    first version of this — matches **"impure"**, and the house convention for extracting a decision
    says in as many words: *place it beside the impure function it serves*. So a docstring that
    mentions its impure caller and the word "pinned" anywhere would have been read as a declaration.
    Found by probing this function's own residual, which is `CORRECTNESS_REPAIRS` §R5b's rule
    applied to the instrument built to enforce a different rule.

    Both failure directions cost something, and they are not symmetric: a false POSITIVE lands a
    healthy function in the sweep, where it almost always reports `consumed` and costs nothing — but
    an unwired impure helper would report a false finding. A false NEGATIVE silently drops a decision
    out of the population the guard claims to cover, which is the exact failure this instrument
    exists to close. Hence tight enough to exclude "impure", loose enough to span the real spellings.
    """
    return bool(_PINNED_TAG.search(docstring))


def declared_decisions(package_dir: str) -> dict[str, str]:
    """Module-level functions in `package_dir` that declare themselves pinned pure decisions.

    Maps ``module.function`` to ``path:line`` so a finding can name where to look. Module level
    only: a nested or method-bound decision is not part of the population this guard claims to
    cover, and claiming more than it checks is what it is here to prevent.
    """
    out: dict[str, str] = {}
    root = pathlib.Path(package_dir)
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and declares_pinned_decision(ast.get_docstring(node) or ""):
                out[f"{path.stem}.{node.name}"] = f"{path}:{node.lineno}"
    return out


def call_counts(roots: tuple[str, ...], names: frozenset[str]) -> dict[str, int]:
    """How many CALL sites each name has under these roots — AST, never text.

    A comment or a docstring mentioning the name is not a call, which is why this cannot be a text
    search: the docstrings in this codebase name sibling decisions constantly, and every one of them
    would read as a consumer.

    Counts ``f(...)`` and ``obj.f(...)`` alike, since the house style reaches decisions through both
    a direct import and a module alias (``_L.state_basis(...)``). See the module docstring for the
    dispatch forms this cannot see.
    """
    counts = dict.fromkeys(names, 0)
    for area in roots:
        base = pathlib.Path(area)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if ".lake" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                if name in counts:
                    counts[name] += 1
    return counts
