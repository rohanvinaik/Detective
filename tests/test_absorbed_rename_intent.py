"""No `getattr(obj, name, default)` reads a name nothing declares — §9 invariant 7 as a standing guard.

EP-G3 (docs/ENGINEERING_PASS_2026-09-26.md). COMMUNICATING_DETERMINISM §9:

    7. An unmeasured input votes zero, and no `getattr(obj, name, default)` stands where a renamed
       field could be absorbed into a silent clean verdict.

A defaulted `getattr` is the one attribute read a rename cannot break loudly: its name is a string,
invisible to the reference graph, and after a rename the default answers forever. Measured when this
was built: 251 such reads in the package; 47 read a fault flag (`budget_exhausted`, `load_failed`,
`stale_target`, …) with a default meaning "no problem", 37 of them in the renderers.

The guard makes the rename loud: every name such a read uses must be declared by the pair (a class
field, method or property; an attribute stored on any object, like the stashes on Wesker's
`ProfilingResult`; a CLI option), by `ast`, or by the data model (a dunder). Names declared elsewhere
take a REASON, as in the sibling guards (`test_pinned_decision_consumption_intent.py`,
`test_consumer_distinction_intent.py`): a bare allow-list is indistinguishable from a hiding place.

KNOWN LIMIT (see `Detective/absorption.py`): a name several classes declare survives a rename on one
of them. That needs the object's static type at each read; the AST does not have it.
"""

from __future__ import annotations

import argparse
import pathlib

import pytest
import Wesker

from Detective.absorption import (
    DATA_MODEL,
    DECLARED,
    EXTERNAL_DECLARED,
    EXTERNAL_STALE,
    UNDECLARED,
    absorption_disposition,
    ast_node_fields,
    declared_attributes,
    getattr_reads,
)
from Detective.cli import _build_parser

# Declared outside Detective and Wesker. Each reason names who declares the attribute and why the
# read needs a default.
EXTERNAL: dict[str, str] = {
    "monitoring": (
        "`sys.monitoring`, Python 3.12+ (PEP 669). On 3.11 there is no monitoring API and None is the "
        "honest answer; `budget.py` reads it to choose its instrument."
    ),
    "co_filename": (
        "A CPython code object's field, read off `getattr(fn, '__code__', None)` — a non-Python callable "
        "has no code object, so the object read can itself be None."
    ),
    "type_params": (
        "`ast.FunctionDef.type_params`, Python 3.12+ (PEP 695). Absent on 3.11, where no function has "
        "type parameters; `decompose_apply` walks them when present."
    ),
    "bound": (
        "`ast.TypeVar.bound`, Python 3.12+ (PEP 695), read off a type-parameter node, which an older "
        "interpreter never produces."
    ),
    "default_value": (
        "`ast.TypeVar.default_value`, Python 3.13+ (PEP 696); absent on 3.12, where a type parameter "
        "has no default."
    ),
}


def _parser_options(parser: argparse.ArgumentParser) -> set[str]:
    out: set[str] = set()
    for action in parser._actions:
        out.add(action.dest)
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                out |= _parser_options(sub)
    return out


@pytest.fixture(scope="module")
def sweep():
    """The reads, what the pair declares (classes, stores, CLI options), and what `ast` declares on
    this interpreter. Kept apart: only the pair can make a registry entry stale."""
    pair = declared_attributes("Detective", str(pathlib.Path(Wesker.__file__).parent))
    pair |= _parser_options(_build_parser())
    return getattr_reads("Detective"), pair, ast_node_fields()


# ---------------------------------------------------------------- the fence


def test_every_defaulted_getattr_reads_a_declared_name(sweep) -> None:
    """THE guard. A name nothing declares is a read whose default is its only possible value — a
    rename already absorbed, or a typo, and in either case a verdict that cannot see what it asks."""
    reads, pair, ast_fields = sweep
    absorbed = [
        r
        for r in reads
        if absorption_disposition(r.name in pair or r.name in ast_fields, r.dunder, EXTERNAL.get(r.name, ""))
        == UNDECLARED
    ]
    assert not absorbed, (
        "getattr(..., default) read(s) of a name nothing declares:\n  "
        + "\n  ".join(
            f"{r.location} in {r.function or '<module>'}: getattr(…, {r.name!r}, {r.default})"
            for r in absorbed
        )
        + "\n\nRestore the field's old name at the read, or add the name to EXTERNAL with who declares it."
    )


def test_the_population_is_not_silently_shrinking(sweep) -> None:
    reads, pair, _ = sweep
    assert len(reads) > 200, f"only {len(reads)} defaulted getattr reads found — the reading likely broke"
    assert len(pair) > 500, f"only {len(pair)} declared names found — the declaration census likely broke"


# ---------------------------------------------------------------- the registry cannot rot


def test_no_registry_entry_names_something_the_pair_now_declares(sweep) -> None:
    """`external_stale`, judged against the PAIR only: `ast` declaring `type_params` on 3.12+ does not
    make that entry stale, because the reason is exactly that it is version-dependent."""
    _, pair, _ = sweep
    stale = [
        name
        for name, reason in EXTERNAL.items()
        if absorption_disposition(name in pair, False, reason) == EXTERNAL_STALE
    ]
    assert not stale, f"the pair declares these now — delete their EXTERNAL entries: {stale}"


def test_no_registry_entry_names_a_read_that_no_longer_exists(sweep) -> None:
    reads, _, _ = sweep
    used = {r.name for r in reads}
    ghosts = [name for name in EXTERNAL if name not in used]
    assert not ghosts, f"EXTERNAL names attributes no getattr reads any more: {ghosts}"


def test_every_reason_actually_says_something() -> None:
    for name, reason in EXTERNAL.items():
        assert len(reason.strip()) > 40, f"{name}: say who declares it and why the read needs a default"


# ---------------------------------------------------------------- the decision, from intent


def test_the_dispositions_read_as_their_names_say() -> None:
    """Hand-written from intent, beside the generated characterization."""
    assert absorption_disposition(True, False, "") == DECLARED
    assert (
        absorption_disposition(True, False, "a reason that no longer applies to anything") == EXTERNAL_STALE
    )
    assert absorption_disposition(False, True, "") == DATA_MODEL
    assert (
        absorption_disposition(False, False, "declared by a library the pair depends on") == EXTERNAL_DECLARED
    )
    assert absorption_disposition(False, False, "   ") == UNDECLARED, "a blank reason is not a reason"


# ---------------------------------------------------------------- the gathering layer (impure)


def _package(tmp_path, source: str) -> tuple[list, frozenset]:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "m.py").write_text(source, encoding="utf-8")
    return getattr_reads(str(pkg)), declared_attributes(str(pkg))


def test_a_renamed_field_is_read_as_undeclared(tmp_path) -> None:
    """The failure this guard exists for: the class moved on, the read did not."""
    reads, declared = _package(
        tmp_path,
        "from dataclasses import dataclass\n\n\n"
        "@dataclass\nclass Result:\n    budget_cut: bool = False\n\n\n"
        "def render(r):\n    return 'CUT' if getattr(r, 'budget_exhausted', False) else 'ok'\n",
    )
    (read,) = reads
    assert read.name == "budget_exhausted" and read.function == "render" and read.default == "False"
    assert absorption_disposition(read.name in declared, read.dunder, "") == UNDECLARED


def test_a_field_stored_on_another_object_counts_as_declared(tmp_path) -> None:
    """Detective stashes attributes on Wesker's results (`result.measurement_basis = ck`)."""
    reads, declared = _package(
        tmp_path,
        "def stash(result, ck):\n    result.measurement_basis = ck\n    setattr(result, 'extra', 1)\n\n\n"
        "def read(result):\n"
        "    return getattr(result, 'measurement_basis', ''), getattr(result, 'extra', 0)\n",
    )
    assert {r.name for r in reads} == {"measurement_basis", "extra"}
    assert {"measurement_basis", "extra"} <= declared


def test_a_method_or_property_counts_as_declared_and_two_argument_getattr_is_not_collected(tmp_path) -> None:
    reads, declared = _package(
        tmp_path,
        "class C:\n    @property\n    def ready(self):\n        return True\n\n\n"
        "def f(c):\n    return getattr(c, 'ready', False), getattr(c, 'loud')\n",
    )
    assert [r.name for r in reads] == ["ready"], "a two-argument getattr raises on a rename: loud already"
    assert "ready" in declared


def test_a_dunder_is_the_data_models(tmp_path) -> None:
    reads, _ = _package(tmp_path, "def f(fn):\n    return getattr(fn, '__wrapped__', None)\n")
    (read,) = reads
    assert read.dunder and absorption_disposition(False, read.dunder, "") == DATA_MODEL
