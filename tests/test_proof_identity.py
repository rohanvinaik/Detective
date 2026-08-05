"""Proof-claim identity (issue #14): every receipt names its two parameters.

A ``PROVEN`` decomposition is a claim parameterized by the mutation policy the
proof suite is complete under (Wesker's ``policy_id``) and the rewrite model
the trial exercised (``transform_class_id``). These tests pin the transform id
the same way Wesker pins its policy id — a golden whose failure message names
the two legal moves — and pin the fingerprint's behavior on engines from
before policy versioning: ``None`` means "policy UNVERSIONED", and the
fingerprint must not invent a suffix for it.
"""

from __future__ import annotations

from types import SimpleNamespace

import Wesker

from Detective.converge import ConvergeResult
from Detective.decompose_apply import (
    TRANSFORM_CLASS_VERSION,
    DecompositionApply,
    transform_class_id,
)
from Detective.verdict_cache import engine_fingerprint, wesker_policy_id

# THE transformation-class identity. When this fails, either the rewrite
# model changed ON PURPOSE — bump TRANSFORM_CLASS_VERSION, update
# _TRANSFORM_SURFACE to describe the new model, and update this golden — or
# you changed the transformer's declared semantics by accident; find out
# which before touching the golden.
GOLDEN_TRANSFORM_CLASS_ID = "1.a22af98fa124"


def test_transform_class_id_is_the_golden():
    assert transform_class_id() == GOLDEN_TRANSFORM_CLASS_ID


def test_transform_class_id_embeds_the_version():
    assert transform_class_id().startswith(f"{TRANSFORM_CLASS_VERSION}.")


def test_policy_id_flows_from_a_policy_publishing_wesker(monkeypatch):
    fake = SimpleNamespace(policy_id="9.deadbeef0123")
    monkeypatch.setattr(Wesker, "mutation_policy", lambda: fake, raising=False)
    assert wesker_policy_id() == "9.deadbeef0123"
    assert engine_fingerprint().endswith("+p9.deadbeef0123")


def test_pre_policy_wesker_reads_as_unversioned_not_unchanged(monkeypatch):
    monkeypatch.delattr(Wesker, "mutation_policy", raising=False)
    assert wesker_policy_id() is None
    fp = engine_fingerprint()
    assert "+p" not in fp
    # The historical format survives verbatim so pre-policy cache entries are
    # invalidated by ENGINE upgrades exactly as before, no more and no less.
    assert fp.startswith("d") and "+w" in fp


def test_receipts_carry_both_identities_with_honest_defaults():
    # The fields exist, default to "unversioned", and are orthogonal: a
    # receipt minted without a policy-publishing engine still names its
    # transformation class.
    receipt = DecompositionApply("f", (), (), (), proof=None)
    assert receipt.policy_id is None
    assert receipt.transform_class_id is None
    stamped = DecompositionApply(
        "f",
        (),
        (),
        (),
        proof=None,
        policy_id="9.deadbeef0123",
        transform_class_id=transform_class_id(),
    )
    assert stamped.policy_id == "9.deadbeef0123"
    assert stamped.transform_class_id == GOLDEN_TRANSFORM_CLASS_ID
    assert (
        ConvergeResult(
            function="f",
            converged=True,
            at_ceiling=True,
            initial_survivors=0,
            final_survivors=0,
            iterations=(),
            written_path=None,
        ).policy_id
        is None
    )
