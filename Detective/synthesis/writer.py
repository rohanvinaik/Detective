"""Assemble synthesized properties into an idiomatic pytest module.

Takes a function's surviving mutants, turns each into an oracle-light property
(:mod:`Detective.synthesis.oracle_light`), and emits a clean, warrant-classed
pytest file: deduped imports, one test per survivor, a docstring stating the
warrant, and ``@pytest.mark.skip`` for properties that still need an oracle
(rather than emitting a failing or vacuous test).

This is where the auto-generation hygiene invariant lives: what Detective writes
is idiomatic, runnable-or-skipped pytest.
"""

from __future__ import annotations

import ast
import sys

from .oracle_light import ExecutableProperty, generate_executable_property

_INDENT = "    "


def synthesize_test_module(
    func_key: str,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef | None,
    survivors: list[dict],
    call_site_inputs: list[dict] | None = None,
    root: str | None = None,
) -> str:
    """Return pytest source pinning each survivor, or "" when there is nothing to write.

    ``root`` reaches `importable_module` so the emitted import matches the repo's own — without
    it a src-layout gets ``from src.pkg.mod import ...``, a second module object for the same
    file, and a suite that silently tests a different program than the one under test.
    """
    props = [generate_executable_property(s, func_key, func_node, call_site_inputs, root) for s in survivors]
    return render_module(func_key, props)


def _ruff_format(source: str) -> str:
    """Hand the emitted module to ruff for its final layout.

    DETECTIVE'S PRODUCT IS A FILE IN SOMEONE ELSE'S REPO, so it has to satisfy that
    repo's CI — and `ruff format --check` is the gate it was failing. Not on style: the
    inputs are 200-character AST snippets (``ast.parse('def _f(x, y):\\n    ...')``), and
    ruff re-lays-out any call that overruns the line budget. That layout cannot be
    reached by choosing nicer line breaks; it is the formatter's algorithm — per-level
    budgets, magic-trailing-comma explosion, bracket-splitting precedence — and it moves
    between ruff versions.

    Which is why this calls ruff instead of imitating it. Imitation was the previous
    strategy and it reads like one: a rule for blank lines after imports, a rule for
    blank lines between defs — each correct, each learned late from a red build, one of
    them recorded as only surfacing once a module had 2+ tests. That is an unbounded
    backlog of rules discovered by someone else's CI; one subprocess ends the category.

    ruff is a declared dependency (a wheel, no system toolchain), so this is not
    best-effort — a repo running Detective has ruff. It still degrades rather than
    crashes: if ruff cannot be invoked or rejects the module, the unformatted source is
    returned, because an ugly-but-valid test is a better outcome than no test. That case
    is a bug in what we emitted, and the file itself is the evidence.
    """
    import subprocess
    import sys

    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell, input via stdin
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--stdin-filename",
                "test_detective_generated.py",
                "-",
            ],
            input=source,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return source
    if proc.returncode != 0 or not proc.stdout.strip():
        return source
    return proc.stdout


def render_module(func_key: str, props: list[ExecutableProperty]) -> str:
    """Render a pytest module from already-built (and possibly filtered) properties.

    The final layout is ruff's, not ours — see :func:`_ruff_format`. What this function
    decides is CONTENT and ORDER (which tests exist, which fold into a parametrize, how
    imports are grouped); what ruff decides is where the lines break. Keeping those two
    jobs apart is the point: the emitted file has to pass `ruff format --check` in the
    repo it lands in, and that is a moving target no hand-written layout can track.
    """
    if not props:
        return ""

    test_name = func_key.rsplit("::", 1)[-1].replace(".", "_")
    call_name = func_key.rsplit("::", 1)[-1]  # the callable name (dotted for methods)
    imports = _collect_imports(props)
    # Every generated test carries @pytest.mark.detective (and needs_oracle ones also
    # @pytest.mark.skip), so pytest is always imported even when no property's own setup
    # pulled it in.
    if "import pytest" not in imports:
        imports.append("import pytest")
    # The target's own top-level package is FIRST-party in the file we emit — it is the
    # module under test, so isort ranks it last. ("pkg/mod.py" -> "pkg"; "mod.py" -> "mod".)
    first_party = func_key.rsplit("::", 1)[0].replace("\\", "/").split("/")[0].removesuffix(".py")
    imports = _isort(imports, first_party)

    # Fold 2+ golden value-captures into ONE @pytest.mark.parametrize test (the idiomatic
    # data-driven form); a single golden and everything else render as individual tests.
    goldens = [p for p in props if p.golden_case is not None]
    blocks: list[str] = []
    if len(goldens) >= 2:
        blocks.append(_render_parametrized(test_name, call_name, goldens))
        rest = [p for p in props if p.golden_case is None]
    else:
        rest = props
    blocks += [_render_test(test_name, i, p) for i, p in enumerate(rest)]

    header = f'"""Auto-generated by Detective — warrant-classed tests for {func_key}."""'
    parts = [header, ""]
    if imports:
        parts += imports + ["", ""]
    parts.append("\n\n\n".join(blocks))
    return _ruff_format("\n".join(parts) + "\n")


def individual_test_names(func_key: str, props: list[ExecutableProperty]) -> dict[str, ExecutableProperty]:
    """Map each INDIVIDUAL rendered test name back to its property, mirroring render_module's
    naming EXACTLY — so a caller (converge) can act on a redundant-test finding from the profile,
    which is keyed by rendered name. Golden captures that fold into the one parametrized test are
    excluded: they are not individually named/droppable here (each case is already minimal-cover
    selected), so a value-pin is never silently dropped."""
    test_name = func_key.rsplit("::", 1)[-1].replace(".", "_")
    goldens = [p for p in props if p.golden_case is not None]
    rest = [p for p in props if p.golden_case is None] if len(goldens) >= 2 else props
    return {
        f"test_{test_name}_{p.category.lower()}_{i}": p for i, p in enumerate(rest) if p.golden_case is None
    }


def _render_parametrized(test_name: str, call_name: str, goldens: list[ExecutableProperty]) -> str:
    """Fold golden value-captures into one ``@pytest.mark.parametrize`` test — the
    idiomatic data-driven form: one test body, N ``(input, expected)`` rows."""
    rows = "\n".join(
        f"{_INDENT}{_INDENT}({args}, {expected}),"
        for args, expected in (g.golden_case for g in goldens if g.golden_case)
    )
    return "\n".join(
        [
            "@pytest.mark.detective",
            '@pytest.mark.parametrize("args, expected", [',
            rows,
            "])",
            f"def test_{test_name}_golden(args, expected):",
            f'{_INDENT}"""VALUE golden captures — pure + deterministic ({len(goldens)} inputs)."""',
            f"{_INDENT}assert {call_name}(*args) == expected",
        ]
    )


def _collect_imports(props: list[ExecutableProperty]) -> list[str]:
    """Deduped import/setup lines across all properties (unordered — see `_isort`)."""
    seen: dict[str, None] = {}
    for p in props:
        for line in p.setup_code.split("\n"):
            line = line.strip()
            if line.startswith(("import ", "from ")):
                seen[line] = None
    return list(seen)


def _top_module(line: str) -> str:
    """The top-level package an import line binds (``from a.b import c`` -> ``a``)."""
    parts = line.split()
    if len(parts) < 2:
        return ""
    return parts[1].split(".")[0].rstrip(",")


def _merge_from_imports(lines: list[str]) -> list[str]:
    """Collapse ``from m import A`` + ``from m import B`` into ``from m import A, B``.

    Names are sorted and deduped inside the merged line, which is what isort emits and so
    what `ruff check` accepts. Plain ``import x`` lines and anything unparseable pass
    through untouched — an import this cannot read is left exactly as the property wrote
    it, since a mangled import costs the caller the whole module and a stray I001 does not.
    Relative imports are keyed by their full ``from`` clause, so ``.a`` and ``..a`` (which
    name different modules) never merge.
    """
    merged: dict[str, list[str]] = {}
    out: list[str] = []
    slot: dict[str, int] = {}
    for line in lines:
        if not line.startswith("from ") or " import " not in line or "*" in line:
            out.append(line)
            continue
        module, names = line.split(" import ", 1)
        if "(" in names or "\\" in names:  # multi-line/continued form: not ours to rewrite
            out.append(line)
            continue
        if module not in merged:
            merged[module] = []
            slot[module] = len(out)
            out.append(line)  # placeholder, rewritten below
        merged[module] += [n.strip() for n in names.split(",") if n.strip()]
    for module, names in merged.items():
        out[slot[module]] = f"{module} import {', '.join(sorted(set(names)))}"
    return out


def _isort(lines: list[str], first_party: str) -> list[str]:
    """Order imports as ruff/isort (I001) does: stdlib, third-party, first-party — groups
    blank-line separated, plain ``import x`` before ``from x import y`` within a group.

    A flat lexicographic sort is NOT this ordering: it puts ``from Detective…`` ahead of
    ``import pytest`` because ``f`` < ``i``. That matters because a project lints the tests
    Detective writes (this one runs `ruff check tests/` in CI), so a generated file must be
    clean AS EMITTED — the hygiene invariant in this module's docstring.

    Same-module ``from`` imports are MERGED, because ordering alone does not satisfy I001.
    Properties contribute their imports independently, so three properties needing three
    names out of one module yielded three ``from m import A`` / ``from m import B`` lines —
    correctly grouped, correctly ordered, and still I001 (isort emits ONE ``from m import
    A, B, C``). Detective's own CI caught it on a file Detective wrote. Merging belongs
    here, not in a `ruff check --fix` pass over the emitted text: over stdin ruff cannot
    know the TARGET's package is first-party, so it ranks it third-party and deletes the
    blank line this function exists to place — trading I001 in one repo for I001 in every
    repo whose config gets first-party right.
    """
    lines = _merge_from_imports(lines)
    groups: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for line in lines:
        top = _top_module(line)
        if top in sys.stdlib_module_names:
            rank = 0
        elif first_party and top == first_party:
            rank = 2
        else:
            rank = 1
        groups[rank].append(line)

    out: list[str] = []
    for rank in (0, 1, 2):
        # `import x` sorts before `from x import y` — isort's default section ordering.
        block = sorted(groups[rank], key=lambda s: (s.startswith("from "), s))
        if block:
            if out:
                out.append("")
            out += block
    return out


def _render_test(fname: str, index: int, prop: ExecutableProperty) -> str:
    """Render one property as a pytest function (skipped when it needs an oracle)."""
    name = f"test_{fname}_{prop.category.lower()}_{index}"
    warrant = _warrant(prop)
    # Tag every generated test so a user can select/deselect them: `pytest -m detective`
    # runs only these; `pytest -m "not detective"` runs only the project's own tests.
    lines: list[str] = ["@pytest.mark.detective"]
    if prop.needs_oracle:
        lines.append(f'@pytest.mark.skip(reason="needs oracle: {_one_line(prop.assertion_code)}")')
    lines.append(f"def {name}():")
    lines.append(f'{_INDENT}"""{warrant}"""')
    lines.extend(f"{_INDENT}{line}" if line else "" for line in prop.assertion_code.split("\n"))
    return "\n".join(lines)


def _warrant(prop: ExecutableProperty) -> str:
    pre = "; ".join(prop.preconditions) if prop.preconditions else "no preconditions"
    mid = f" [{prop.mutant_id}]" if prop.mutant_id else ""
    return f"{prop.category} survivor{mid} — {pre} (confidence {prop.confidence})."


def _one_line(text: str) -> str:
    """First non-comment line of an assertion, collapsed for a skip reason."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return text.split("\n")[0].strip()
