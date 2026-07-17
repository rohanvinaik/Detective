"""Design-warranted tests for Detective.purity, mutation-driven to the ceiling.

Plain module-level helpers only (no fixtures).
"""

from __future__ import annotations

import ast

from Detective.purity import (
    PurityResult,
    _param_names,
    analyze_function,
    get_name,
    is_pure,
    world_effects,
)


def _fn(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def _inner(src: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


# ── pure ──────────────────────────────────────────────────────────
def test_pure_arithmetic():
    assert is_pure(_fn("def f(a, b):\n return a + b")) is True


def test_local_variable_mutation_is_pure():
    assert is_pure(_fn("def f():\n items = []\n items.append(1)\n return items")) is True


def test_init_self_assignment_is_pure():
    # constructing instance state in __init__ is not a mutation
    assert is_pure(_fn("def __init__(self):\n self.x = 1"), is_method=True) is True


# ── impure: scope writes ──────────────────────────────────────────
def test_global_write_impure():
    assert is_pure(_fn("def f():\n global x\n x = 1")) is False


def test_nonlocal_write_impure():
    r = analyze_function(_inner("def outer():\n y = 0\n def f():\n  nonlocal y\n  y = 1", "f"))
    assert r.is_pure is False
    assert r.reasons == ("writes nonlocal 'y'",)


def test_annotated_local_prevents_false_external_flag():
    # `x: list = []` registers x as local via visit_AnnAssign, so x.append() is a
    # local mutation (pure), not an external one.
    assert is_pure(_fn("def f():\n x: list = []\n x.append(1)\n return x")) is True


def test_annotated_attribute_assignment_is_impure():
    # `self.x: int = 1` in a method is an instance mutation, not a local.
    assert _reasons("def m(self):\n self.x: int = 1", True) == ("assigns instance state self.x",)


def test_annotated_subscript_target_is_pure():
    # a Subscript AnnAssign target on a local object is neither Name nor Attribute
    assert is_pure(_fn("def f():\n d = {}\n d[0]: int = 1\n return d")) is True


# ── impure: external mutation ─────────────────────────────────────
def test_method_self_mutation_impure():
    assert is_pure(_fn("def m(self):\n self.x = 1"), is_method=True) is False


def test_external_attribute_assign_impure():
    assert is_pure(_fn("def f():\n obj.x = 1")) is False


def test_external_subscript_write_impure():
    assert is_pure(_fn("def f():\n data[0] = 1")) is False


def test_augassign_external_attribute_impure():
    assert is_pure(_fn("def m(self):\n self.count += 1"), is_method=True) is False


def test_augassign_external_subscript_impure():
    assert is_pure(_fn("def f():\n totals[0] += 1")) is False


def test_delete_external_impure():
    assert is_pure(_fn("def f():\n del cache[0]")) is False


def test_external_mutating_method_impure():
    assert is_pure(_fn("def f(x):\n data.append(x)")) is False


def test_path_write_method_impure():
    assert is_pure(_fn("def f(p):\n p.write_text('x')")) is False


# ── impure: I/O + generators + defaults ───────────────────────────
def test_impure_builtin_impure():
    assert is_pure(_fn("def f(x):\n print(x)")) is False


def test_generator_impure():
    assert is_pure(_fn("def f():\n yield 1")) is False


def test_yield_from_impure():
    assert is_pure(_fn("def f(xs):\n yield from xs")) is False


def test_mutable_default_impure():
    assert is_pure(_fn("def f(items=[]):\n return items")) is False


# ── result + helpers ──────────────────────────────────────────────
def test_analyze_function_reports_reasons():
    r = analyze_function(_fn("def f():\n global x\n x = 1"))
    assert isinstance(r, PurityResult)
    assert r.is_pure is False
    assert r.reasons == ("writes global 'x'",)


def test_pure_result_has_no_reasons():
    assert analyze_function(_fn("def f(a):\n return a")).reasons == ()


def test_get_name_name_attribute_and_other():
    assert get_name(ast.parse("a", mode="eval").body) == "a"
    assert get_name(ast.parse("a.b.c", mode="eval").body) == "a.b.c"
    assert get_name(ast.parse("1", mode="eval").body) is None


def test_param_names_covers_all_arg_kinds():
    fn = _fn("def f(a, /, b, *args, c, **kw):\n return a")
    assert _param_names(fn.args) == {"a", "b", "args", "c", "kw"}


# ── exact reasons (pin the message templates) ─────────────────────
def _reasons(src: str, method: bool = False) -> tuple[str, ...]:
    return analyze_function(_fn(src), is_method=method).reasons


def test_exact_reason_strings():
    assert _reasons("def m(self):\n self.x = 1", True) == ("assigns instance state self.x",)
    assert _reasons("def f():\n obj.x = 1") == ("assigns external obj.x",)
    assert _reasons("def f():\n data[0] = 1") == ("subscript-writes external data",)
    assert _reasons("def m(self):\n self.c += 1", True) == ("augments instance state self.c",)
    assert _reasons("def f():\n totals[0] += 1") == ("augments external subscript totals",)
    assert _reasons("def f():\n del cache[0]") == ("deletes external cache",)
    assert _reasons("def f(x):\n data.append(x)") == ("mutates external via .append()",)
    assert _reasons("def f(p):\n p.write_text('x')") == ("filesystem write via .write_text()",)
    assert _reasons("def f(x):\n print(x)") == ("calls impure builtin print",)
    assert _reasons("def f():\n yield 1") == ("is a generator (yield)",)
    assert _reasons("def f(xs):\n yield from xs") == ("is a generator (yield from)",)
    assert _reasons("def f(i=[]):\n return i") == ("mutable default argument",)


def test_dotted_impure_builtin_via_split():
    # name="open.write" is not in the set, but split(".")[0]="open" is -> flagged
    assert _reasons("def f():\n open.write()") == ("calls impure builtin open.write",)


def test_cls_method_mutation_impure():
    assert is_pure(_fn("def m(cls):\n cls.registry = 1"), is_method=True) is False


def test_local_name_assign_stays_pure():
    # assigning a plain local Name adds it as local; no side effect
    assert is_pure(_fn("def f():\n y = 1\n z = y + 1\n return z")) is True


# ── discriminating inputs for isinstance/logical branches ─────────
def test_immutable_default_is_pure():
    # a non-mutable default (int) must NOT be flagged (kills isinstance->True)
    assert is_pure(_fn("def f(x=5):\n return x")) is True


def test_local_subscript_assign_is_pure():
    # local[key] = v is not external (kills the Subscript `and external` -> `or`)
    assert is_pure(_fn("def f():\n d = {}\n d[0] = 1\n return d")) is True


def test_tuple_target_assign_is_pure():
    # a tuple target is neither Name/Attribute/Subscript (kills Subscript isinstance->True)
    assert is_pure(_fn("def f():\n a, b = 1, 2\n return a")) is True


def test_local_name_delete_is_pure():
    # deleting a local name is not a side effect; a plain Name (not Subscript) target
    assert is_pure(_fn("def f():\n y = 1\n del y")) is True


def test_external_name_delete_is_impure():
    assert _reasons("def f():\n del registry") == ("deletes external registry",)


def test_local_subscript_augassign_is_pure():
    assert is_pure(_fn("def f():\n d = {}\n d[0] += 1\n return d")) is True


def test_local_name_augassign_is_pure():
    # a Name aug-target is neither Attribute nor Subscript (kills Subscript isinstance->True)
    assert is_pure(_fn("def f():\n x = 0\n x += 1\n return x")) is True


# ── world_effects (is it safe to call this with an argument we INVENTED?) ──
# A different question from `is_pure`, kept separate because `is_pure` was measured answering it
# wrong in BOTH directions: it calls `shutil.rmtree` PURE, and calls `list.append` impure.
def test_the_bug_this_exists_for_open_for_writing():
    # `_declare_pythonpath("")` resolved `pyproject.toml` against the CWD and rewrote this
    # repository's own config — the str grid is `["", "a", "abc"]`, and `open(p, "w")` CREATES.
    assert world_effects(_fn('def f(p):\n with open(p, "w") as fh:\n  fh.write("x")')) == (
        "opens a file for writing",
    )


def test_reading_a_file_is_not_an_effect():
    # `open(p)` cannot damage anything, and banning it would cost every parser and loader.
    assert world_effects(_fn("def f(p):\n return open(p).read()")) == ()


def test_an_unreadable_mode_is_assumed_to_be_a_write():
    # Guessing "probably a read" is how a guard becomes decorative.
    assert world_effects(_fn("def f(p, mode):\n return open(p, mode)")) == ("opens a file for writing",)


def test_rmtree_is_an_effect_even_though_is_pure_calls_it_pure():
    # DEMONSTRATED, not argued: with this guard disabled, `converge` on a function calling
    # `shutil.rmtree(target: str)` DELETED a directory named `a` — because the str grid contains
    # "a". `is_pure` returns True here: rmtree returns None and mutates nothing in-process.
    node = _fn("def f(p):\n shutil.rmtree(p)")
    assert world_effects(node) == ("calls shutil.rmtree()",)
    assert is_pure(node) is True  # the whole reason this predicate had to be separate


def test_subprocess_is_an_effect():
    assert world_effects(_fn("def f(c):\n subprocess.run([c])")) == ("calls subprocess.run()",)


def test_network_is_an_effect():
    assert world_effects(_fn("def f(u):\n requests.post(u)")) == ("calls requests.post()",)


def test_os_removal_is_an_effect():
    assert world_effects(_fn("def f(p):\n os.remove(p)")) == ("filesystem/process call os.remove()",)


def test_path_write_through_a_call_receiver_is_seen():
    # `get_name` cannot name a Call receiver, so reading the method off it returned None and the
    # branch never fired — `Path(p).write_text(...)`, the most common way Python writes a file,
    # read as effect-free. The attr is taken from the node directly.
    assert world_effects(_fn('def f(p):\n Path(p).write_text("x")')) == (
        "filesystem write via .write_text()",
    )


def test_str_replace_is_not_a_filesystem_move():
    # `Path.replace(target)` takes ONE arg; `s.replace(a, b)` takes two. Arity disambiguates.
    assert world_effects(_fn('def f(s):\n return s.replace("a", "b")')) == ()


def test_harmless_impurity_is_not_an_effect():
    # `append` and `print` are impure and completely safe to call with a made-up value. Gating on
    # `is_pure` would abstain on both and cost coverage for nothing.
    assert world_effects(_fn("def f(items, x):\n items.append(x)")) == ()
    assert world_effects(_fn("def f(x):\n print(x)")) == ()


def test_a_pure_function_has_no_effects():
    assert world_effects(_fn("def f(a, b):\n return a + b")) == ()


def test_effects_are_deduped_but_ordered():
    node = _fn('def f(p, q):\n open(p, "w")\n open(q, "a")\n shutil.rmtree(p)')
    assert world_effects(node) == ("opens a file for writing", "calls shutil.rmtree()")
