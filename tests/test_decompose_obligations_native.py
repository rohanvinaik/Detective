"""Intent tests for the decompose interface contract (issue #16).

THE DEFECT. ``decompose --apply`` proved a rewrite behavior-preserving by ONE bit: rerun the
mutation-complete suite, green → apply. That bit is silent about γ — the interface obligations a
block carries across the new call boundary. A dimension the mutation universe never exercised
(an in-place mutation of an input, an ordered side effect, a relocatable-only closure) was
discharged by assumption, not by proof, and a PROVEN claim could not NAME which obligations it
had actually established. #16 makes γ explicit: every extraction carries an ``InterfaceContract``
of typed obligations, each with an evidence basis, and an ``unsupported`` obligation forces
proposal-only rather than riding a green rerun into an auto-apply.

These are authored from intent, not generated: a characterization suite would pin whatever the
code does today, including a wrong classification. The synth suites pin ``apply_disposition`` and
``trial_verdict`` (the pure decisions); this file pins the MEANING of the model and that the live
``extract_candidate`` path actually populates the contract from the finder's interface.
"""

from __future__ import annotations

import ast

from Detective.decompose import (
    InterfaceContract,
    InterfaceObligation,
    apply_disposition,
    contract_apply_disposition,
    find_extraction_candidates,
    interface_obligations,
    trial_verdict,
)
from Detective.decompose_apply import extract_candidate


def _block(src: str) -> list[ast.stmt]:
    return ast.parse(src).body


# ── the model: what each dimension's evidence basis is ──────────────────────


def test_value_flow_is_structural():
    c = interface_obligations(_block("t = a + b\nu = t * 2\n"), inputs=["a", "b"], outputs=["u"])
    kinds = {(o.kind, o.subject): o.evidence for o in c.obligations}
    assert kinds[("value_in", "a")] == "structural"
    assert kinds[("value_in", "b")] == "structural"
    assert kinds[("value_out", "u")] == "structural"
    # value flow alone carries nothing weaker than structural, so it auto-applies
    assert contract_apply_disposition(c) == "apply"


def test_in_place_method_mutation_of_an_input_is_a_witnessed_obligation():
    c = interface_obligations(_block("acc.append(x)\n"), inputs=["acc", "x"], outputs=[])
    got = {(o.kind, o.subject): o.evidence for o in c.obligations}
    assert got.get(("alias_mutation", "acc")) == "witnessed"
    # x is only read, never mutated → no alias obligation for it
    assert ("alias_mutation", "x") not in got


def test_subscript_and_attribute_stores_into_an_input_are_alias_mutations():
    c_sub = interface_obligations(_block("d[k] = v\n"), inputs=["d", "k", "v"], outputs=[])
    assert any(o.kind == "alias_mutation" and o.subject == "d" for o in c_sub.obligations)
    c_attr = interface_obligations(_block("obj.count += 1\n"), inputs=["obj"], outputs=[])
    assert any(o.kind == "alias_mutation" and o.subject == "obj" for o in c_attr.obligations)


def test_a_plain_rebinding_of_an_input_is_not_an_alias_mutation():
    # `n = n + 1` rebinds the local name; it does NOT mutate the caller's object, so it is
    # value flow, not an alias obligation. Conflating the two would refuse safe extractions.
    c = interface_obligations(_block("n = n + 1\n"), inputs=["n"], outputs=["n"])
    assert not any(o.kind == "alias_mutation" for o in c.obligations)


def test_discarded_call_is_an_ordered_effect():
    c = interface_obligations(_block("log(msg)\nout = compute(msg)\n"), inputs=["msg"], outputs=["out"])
    assert any(o.kind == "effect_order" for o in c.obligations)
    # a block with no bare-call statement carries no effect_order obligation
    c2 = interface_obligations(_block("out = compute(msg)\n"), inputs=["msg"], outputs=["out"])
    assert not any(o.kind == "effect_order" for o in c2.obligations)


def test_obligations_are_sorted_for_a_byte_stable_contract():
    c = interface_obligations(_block("acc.append(x)\nlog(x)\n"), inputs=["x", "acc"], outputs=[])
    kinds = [(o.kind, o.subject) for o in c.obligations]
    assert kinds == sorted(kinds)


# ── the gate: unsupported forces proposal-only, nothing else does ───────────


def test_disposition_refuses_only_on_unsupported():
    assert apply_disposition(["structural", "witnessed", "mutation_pinned"]) == "apply"
    assert apply_disposition([]) == "apply"  # an empty contract is vacuously appliable
    assert apply_disposition(["structural", "unsupported"]) == "refuse_unsupported"


def test_contract_disposition_projects_then_defers():
    unsup = InterfaceContract((InterfaceObligation("closure_cell", "f", "unsupported"),))
    assert contract_apply_disposition(unsup) == "refuse_unsupported"
    clean = InterfaceContract((InterfaceObligation("value_in", "a", "structural"),))
    assert contract_apply_disposition(clean) == "apply"


# ── the trial decision the apply loop consumes ──────────────────────────────


def test_trial_verdict_four_outcomes():
    # green + admissible → proven (auto-appliable)
    assert trial_verdict(True, True, "apply") == "proven"
    # green but an unsupported obligation → witnessed, NOT rejected (proposal-only)
    assert trial_verdict(True, True, "refuse_unsupported") == "witnessed"
    # a suite existed and went red → rejected
    assert trial_verdict(False, True, "apply") == "rejected"
    # no suite ever ran → unproven, NOT rejected
    assert trial_verdict(False, False, "apply") == "unproven"


def test_witnessed_is_never_rejected_even_without_a_disposition_apply():
    # the disposition can only WITHHOLD a green trial, never turn it into a rejection
    assert trial_verdict(True, True, "refuse_unsupported") != "rejected"


# ── the plumbing: the live extract_candidate path fills the contract ────────

_SRC = (
    "def f(a, b, c):\n"
    "    base = a * 2\n"
    "    if a > 10:\n"
    "        x = 1\n"
    "    elif a > 5:\n"
    "        x = 2\n"
    "    else:\n"
    "        x = 3\n"
    "    if b:\n"
    "        x += c\n"
    "    total = x + base\n"
    "    return total\n"
)


def test_extract_candidate_populates_a_contract_matching_the_interface():
    cands = find_extraction_candidates(ast.parse(_SRC).body[0])
    assert cands
    ex = extract_candidate(_SRC, "f", cands[0])
    assert ex is not None
    # every input becomes exactly one value_in obligation; every output one value_out — the
    # serialized contract is tied to the finder's interface, so dropping the plumbing is caught.
    value_ins = sorted(o.subject for o in ex.contract.obligations if o.kind == "value_in")
    value_outs = sorted(o.subject for o in ex.contract.obligations if o.kind == "value_out")
    assert value_ins == sorted(cands[0].inputs)
    assert value_outs == sorted(cands[0].outputs)
    # a clean value-flow extraction is appliable
    assert contract_apply_disposition(ex.contract) == "apply"
