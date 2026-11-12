"""The field-consumption fence: every dataclass field is read, reaches a consumer, or says why.

THE DEFECT (Detective#94, EP-G2, founder ruling ENGINEERING_PASS §6 item 18: "every computed field is
read, or it goes"): `consumption.py` guards that every pinned FUNCTION has a consumer. A dataclass FIELD
that production computes and nothing reads is invisible to it: `capability_flags` rode through every
layer for a wave with no reader. Measured on 2026-11-12, by AST over `Detective/`: 631 fields in the
package's dataclasses, 54 of which no production code reads by name.

The by-name reading OVERSTATES unreadness (COMMUNICATING_DETERMINISM §11): `asdict` emits a whole object,
so a field reaches `--json` without any attribute being read. That is not a free pass either, so the
exemption is VERIFIED: a field counts as `reflected` only when its class is reachable, through field
annotations, from a root that a named site really emits (`asdict` in that function) or that the package
exports as its public return type, and `test_reflection_roots_are_what_they_claim` re-checks both. The
number of fields resting on that route is pinned, so a new reflected-only field is a deliberate edit.

The registries follow `test_pinned_decision_consumption_intent.py`, and for its reason: *"the solution isn't
to hide from the dark, it's to throw some light on it"*. An entry takes a REASON, never a bare name:

    BY_DESIGN  the field is meant to be unread by name, and the reason names what consumes it.
    OPEN       a computed field nothing consumes. A real gap, carried in the open until it is wired
               to the page/`--json` where its meaning belongs, or deleted with its producer.
"""

from __future__ import annotations

import pytest

import Detective
from Detective.field_consumption import (
    EXEMPT_DECLARED,
    READ,
    REFLECTED,
    REGISTRY_STALE,
    TEST_ONLY,
    UNREAD,
    class_graph,
    dataclass_fields,
    field_consumption_disposition,
    field_read_counts,
    reachable_classes,
    reflection_site_tokens,
    reflection_sites,
)

# A root that EMITS whole objects: ("asdict", "module.function") names the function that calls `asdict` on
# it into `--json`; ("api", name) names a public return type exported in `Detective.__all__`.
REFLECTION_ROOTS: dict[str, tuple[str, str]] = {
    "ConvergeResult": ("asdict", "cli._run_converge"),
    "SuiteAudit": ("asdict", "cli._run_audit"),
    "ScopeMap": ("asdict", "cli._run_diagnose"),
    "DecompositionApply": ("asdict", "cli._run_decompose"),
    "CertifyResult": ("api", "CertifyResult"),
}

BY_DESIGN: dict[str, str] = {
    "capture.HarvestResult.samples": (
        "Consumed through the Sequence protocol the class implements over it: `__len__`, `__getitem__` and "
        "the iteration they give every `for sample in harvest` / `len(harvest)` consumer. Those dunders "
        "are the reads; there is deliberately no `.samples` attribute access at the call sites, which "
        "treat the result as the tuple of sample tuples it stands in for (its docstring)."
    ),
    "equivalents.EquivalenceFlag.diff": (
        "The flag's stable identity, persisted whole by asdict@equivalents.save_flags into the human store "
        "and reconstructed by `load_flags`. The in-memory key is derived from it at write time "
        "(`flag_key(func_key, diff)`), so no reader needs the attribute while the store round-trips it."
    ),
    "distinction.ConsumerRead.codes": (
        "A record of the invariant-3 guard (`Detective/distinction.py`), a repo-discipline instrument "
        "deliberately not wired to any verb; its consumer is tests/test_consumer_distinction_intent.py "
        "(`r.codes`), as the function guard's own entries are."
    ),
}

OPEN: dict[str, str] = {
    "adequacy.FaultOutcome.family": (
        "`run_adequacy` has no caller outside adequacy.py (listed in ARCHITECTURE.md as the benchmark "
        "entry point), so no verb or page reads the report; only its test builds one. Wire it to a verb "
        "(`adequacy` on a proven extraction) or retire the benchmark."
    ),
    "adequacy.AdequacyReport.abstain_reason": (
        "Same unwired benchmark as FaultOutcome.family: `adequate` reads it inside the class, and nothing "
        "reads `adequate`. An abstention is the report declining to make a claim, and today no reader "
        "is told so."
    ),
    "binding.TargetBinding.receiver_params": (
        "Computed twice (`classify_target`, `binding_from_node`) as 'how many LEADING parameters are the "
        "receiver, which input synthesis must skip', and read by nothing: about fifteen sites re-derive the "
        "skip by PARAMETER NAME (`a.arg not in ('self', 'cls')`) in engine, equivalence, extract, survey, "
        "oracle_light and cli. That is a narrower proxy of a computed fact (invariant 8). Not deleted "
        "because the pinned classify_target golden (tests/detective) reprs it; the fix is to make those "
        "sites consume the binding."
    ),
    "regime.FileIdentity.dev": (
        "FileIdentity is landed ahead of its consumer (docs/TEST_BASIS.md B1: 'Land the identity types ... "
        "No deletions') and is never instantiated anywhere, so its equality on (dev, ino) consumes nothing "
        "yet. Wire it at the live-session identity check, or drop the type from the plan."
    ),
    "regime.FileIdentity.ino": "Same type, same reason as FileIdentity.dev: declared by B1, never built.",
    "regime.RevisionId.content_digest": (
        "RevisionId is landed ahead of its consumer (docs/TEST_BASIS.md B1) and never instantiated; the "
        "across-run cache identity it models is still keyed elsewhere. Wire it or drop it from the plan."
    ),
    "regime.RevisionId.context_digest": "Same type, same reason as RevisionId.content_digest.",
    "plan.PlanResolution.file": (
        "Set at three construction sites beside `function`, read by no consumer (the renderer reads "
        "`refusal`, `assembly`, `detail`, `regime`). Only a test reads it. Delete it with its producers, "
        "or let the refusal page name the file."
    ),
    "suite_edit.RemovalReport.not_found": (
        "A derived view of `outcomes` (the ids whose code is not removed / parametrized_row), kept after "
        "#103 made `outcomes` the complete per-id record the --remove page reads. Only "
        "tests/test_suite_edit_native.py and tests/test_removal_identity_intent.py assert it. Delete it "
        "and move those asserts onto `outcomes`."
    ),
    "suite_edit.RemovalReport.parametrized": (
        "A derived view of `outcomes` (the ids coded parametrized_row); the --remove page reads the code "
        "per id. Only tests read it. Delete it with `not_found`."
    ),
    "oracle_light.ExecutableProperty.confidence": (
        "A hand-set number (0.2 to 0.95) at about thirty construction sites. `property_identity` states it "
        "is DELIBERATELY EXCLUDED from identity and nothing ranks, filters or prints by it; pins.json "
        "persists it. Delete the field, its producers and the nine test files that construct it, with a "
        "pins.json schema bump."
    ),
    "oracle_light.ExecutableProperty.source_lenses": (
        "Same as `confidence`: excluded from identity, persisted in pins.json, read by nothing."
    ),
}


def _key(module_class_field: str) -> str:
    return module_class_field


@pytest.fixture(scope="module")
def sweep():
    """One AST pass: the fields, the production and test reads of each, and the reflection reach."""
    fields = dataclass_fields("Detective")
    production = field_read_counts(("Detective",), fields)
    elsewhere = field_read_counts(("tests", "dev", "scripts"), fields)
    graph = class_graph("Detective")
    reach = {root: reachable_classes(graph, root) for root in REFLECTION_ROOTS}

    def via(key: str) -> str:
        cls = key.split(".")[-2]
        return next(
            (f"{kind}@{site}" for root, (kind, site) in REFLECTION_ROOTS.items() if cls in reach[root]), ""
        )

    return fields, production, elsewhere, {k: via(k) for k in fields}


def _code(sweep, key: str, reason: str = "") -> str:
    _fields, production, elsewhere, reflected = sweep
    return field_consumption_disposition(production[key], elsewhere[key], reflected[key], reason)


# ---------------------------------------------------------------- the fence


def test_every_field_is_read_reflected_or_carries_a_reason(sweep) -> None:
    """THE guard. A computed field nothing reads, with nothing on record saying why, is the
    `capability_flags` shape, and it passes every other check in this repo."""
    fields = sweep[0]
    orphans = [
        key
        for key in fields
        if _code(sweep, key) in (UNREAD, TEST_ONLY) and key not in BY_DESIGN and key not in OPEN
    ]
    assert not orphans, (
        "dataclass field(s) that no production code reads, no verified emission reaches, and no registry "
        "entry explains:\n  "
        + "\n  ".join(f"{k}  ({fields[k]})  [{_code(sweep, k)}]" for k in orphans)
        + "\n\nWire it to the page/--json where its meaning belongs, delete it and its producer, or add "
        "it to BY_DESIGN/OPEN with a reason a reader can check."
    )


def test_the_population_is_not_silently_shrinking(sweep) -> None:
    """A broken reader drops fields out of the population the guard claims to cover, which would read as
    'every field is consumed'. Pinned loosely: it moves as fields are added; a COLLAPSE is caught."""
    fields, production, _e, _r = sweep
    assert len(fields) > 550, f"only {len(fields)} dataclass fields found - the dataclass reader likely broke"
    assert sum(1 for v in production.values() if v > 0) > 450, (
        "production reads collapsed - the read matcher broke"
    )


def test_reflection_roots_are_what_they_claim() -> None:
    """The reflected exemption is only as good as its roots: each asdict root's site must really call a
    reflective emitter, each API root must really be exported, and every root must be a dataclass."""
    sites = reflection_sites("Detective")
    graph = class_graph("Detective")
    for root, (kind, site) in REFLECTION_ROOTS.items():
        assert root in graph, f"{root} is not a dataclass in the package"
        if kind == "asdict":
            assert "asdict" in sites.get(site, frozenset()), f"{site} does not call a reflective emitter"
        else:
            assert kind == "api" and site in Detective.__all__, f"{site} is not exported by Detective.__all__"


def test_the_number_of_reflected_only_fields_is_deliberate(sweep) -> None:
    """Every field resting on reflection alone, counted. A new one is a field that reaches `--json` or a
    library caller and no attribute read: legitimate, but a decision, so it is a visible edit here."""
    fields = sweep[0]
    reflected = [k for k in fields if _code(sweep, k) == REFLECTED]
    assert len(reflected) == 35, f"{len(reflected)} reflected-only fields: {sorted(reflected)}"


# ---------------------------------------------------------------- the registries cannot rot


def test_no_registry_entry_names_a_field_that_is_now_read(sweep) -> None:
    """`registry_stale`: an excuse that outlived its reason is a finding, not a tidy no-op."""
    stale = [
        k for k, r in {**BY_DESIGN, **OPEN}.items() if k in sweep[0] and _code(sweep, k, r) == REGISTRY_STALE
    ]
    assert not stale, f"these fields are read now; delete their registry entries: {stale}"


def test_no_registry_entry_names_a_field_that_no_longer_exists(sweep) -> None:
    ghosts = [k for k in {**BY_DESIGN, **OPEN} if k not in sweep[0]]
    assert not ghosts, f"registry names fields that do not exist any more: {ghosts}"


def test_every_registered_field_is_actually_unread(sweep) -> None:
    for key, reason in {**BY_DESIGN, **OPEN}.items():
        assert _code(sweep, key, reason) == EXEMPT_DECLARED, key


def test_every_reason_actually_says_something() -> None:
    for key, reason in {**BY_DESIGN, **OPEN}.items():
        assert len(reason.strip()) > 40, f"{key}: say what consumes it, or what it needs"


def test_a_reflection_claim_names_a_site_that_does_it() -> None:
    """A reason that says a field is emitted by `asdict`, or compared by a generated `__eq__`, must NAME the
    site (`asdict@module.function`), and the function must really contain that reflection."""
    sites = reflection_sites("Detective")
    for key, reason in {**BY_DESIGN, **OPEN}.items():
        tokens = reflection_site_tokens(reason)
        claims = any(w in reason for w in ("asdict", "to_json", "__eq__", "__hash__"))
        assert tokens or not claims, f"{key}: claims reflection without an `asdict@module.function` site"
        for kind, site in tokens:
            assert kind in sites.get(site, frozenset()) or (kind == "eq" and "eq" in sites.get(site, ())), (
                f"{key}: {site} does not do {kind}"
            )


def test_a_field_is_never_in_both_registries() -> None:
    assert not (set(BY_DESIGN) & set(OPEN))


def test_the_open_gaps_are_exactly_what_we_know_about() -> None:
    """`len(OPEN)` is the number this guard exists to make visible. A fix makes it go DOWN; a new finding
    UP. Either is a deliberate edit here, never a silent drift."""
    assert len(OPEN) == 12


# ---------------------------------------------------------------- the decision


@pytest.mark.parametrize(
    ("production", "tests", "via", "reason", "expected"),
    [
        (3, 0, "", "", READ),
        (1, 5, "asdict@cli.f", "", READ),
        (1, 0, "", "consumed via X", REGISTRY_STALE),
        (0, 0, "", "consumed via X", EXEMPT_DECLARED),
        (0, 4, "asdict@cli.f", "consumed via X", EXEMPT_DECLARED),
        (0, 0, "asdict@cli.f", "", REFLECTED),
        (0, 2, "asdict@cli.f", "", REFLECTED),
        (0, 2, "", "", TEST_ONLY),
        (0, 0, "", "", UNREAD),
        (0, 0, "", "   ", UNREAD),  # silence cannot buy silence
        (0, 0, "   ", "", UNREAD),
        (0, 3, "", "\n", TEST_ONLY),
    ],
)
def test_the_disposition_truth_table(production, tests, via, reason, expected) -> None:
    assert field_consumption_disposition(production, tests, via, reason) == expected


# ---------------------------------------------------------------- the gathering layer, on a scratch package


def _scratch(tmp_path, source: str, tests: str = ""):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "m.py").write_text(source, encoding="utf-8")
    tdir = tmp_path / "t"
    tdir.mkdir()
    (tdir / "test_m.py").write_text(tests, encoding="utf-8")
    fields = dataclass_fields(str(pkg))
    return str(pkg), str(tdir), fields


_SCRATCH = """
from dataclasses import dataclass, field
from typing import ClassVar

@dataclass(frozen=True)
class Inner:
    seen: int
    kept: int = 0

@dataclass
class Outer:
    inner: Inner
    used: int = 0
    planted: int = 0  # the field the guard must catch
    stamped: int = 0
    by_name: int = 0
    via_property: int = 0
    via_dunder: int = 0
    KIND: ClassVar[int] = 1

    @property
    def derived(self) -> int:
        return self.via_property

    def __repr__(self) -> str:
        return str(self.via_dunder)

def consume(o: Outer) -> int:
    o.stamped = 5
    Outer(Inner(1), planted=2)
    return o.used + o.inner.seen + getattr(o, "by_name") + o.derived
"""


def test_a_planted_unread_field_is_caught(tmp_path) -> None:
    """The acceptance: a NEW field nobody reads fails the guard. Planted in a scratch package."""
    pkg, tests, fields = _scratch(tmp_path, _SCRATCH)
    counts = field_read_counts((pkg,), fields)
    unread = sorted(k.split(".", 1)[1] for k, v in counts.items() if v == 0)
    assert unread == ["Inner.kept", "Outer.planted", "Outer.stamped", "Outer.via_dunder"]
    assert field_consumption_disposition(counts["m.Outer.planted"], 0, "", "") == UNREAD


def test_what_is_and_is_not_a_read(tmp_path) -> None:
    pkg, _tests, fields = _scratch(tmp_path, _SCRATCH)
    counts = field_read_counts((pkg,), fields)
    assert counts["m.Outer.used"] == 1  # an attribute load outside the class
    assert counts["m.Inner.seen"] == 1  # a nested load
    assert counts["m.Outer.by_name"] == 1  # getattr(obj, "name") is the string spelling of a read
    assert counts["m.Outer.stamped"] == 0  # a store is the producer, not a reader
    assert counts["m.Outer.planted"] == 0  # a constructor keyword is the producer too
    assert counts["m.Outer.via_property"] == 1  # read in a property that is itself read outside the class
    assert counts["m.Outer.via_dunder"] == 0  # a dunder's own-body read is not a consumer
    assert "m.Outer.KIND" not in fields  # a ClassVar is not an instance field


def test_a_test_read_is_counted_apart(tmp_path) -> None:
    pkg, tests, fields = _scratch(tmp_path, _SCRATCH, "def test_x(o):\n    assert o.planted == 2\n")
    assert field_read_counts((pkg,), fields)["m.Outer.planted"] == 0
    assert field_read_counts((tests,), fields)["m.Outer.planted"] == 1
    assert field_consumption_disposition(0, 1, "", "") == TEST_ONLY


def test_reflection_reach_follows_annotations(tmp_path) -> None:
    pkg, _tests, _fields = _scratch(tmp_path, _SCRATCH)
    graph = class_graph(pkg)
    assert reachable_classes(graph, "Outer") == {"Outer", "Inner"}
    assert reachable_classes(graph, "Inner") == {"Inner"}
    assert reachable_classes(graph, "Nope") == {"Nope"}


def test_reflection_sites_see_asdict_and_equality(tmp_path) -> None:
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "s.py").write_text(
        "from dataclasses import asdict\n"
        "def emit(x):\n    return asdict(x)\n"
        "def same(a, b):\n    return a == b\n"
        "def neither(a):\n    return a + 1\n",
        encoding="utf-8",
    )
    sites = reflection_sites(str(pkg))
    assert sites["s.emit"] == {"asdict"}
    assert sites["s.same"] == {"eq"}
    assert sites["s.neither"] == frozenset()


def test_a_missing_or_unparseable_root_is_not_an_error(tmp_path) -> None:
    (tmp_path / "bad.py").write_text("def (:\n", encoding="utf-8")
    assert dataclass_fields(str(tmp_path / "nowhere")) == {}
    assert dataclass_fields(str(tmp_path)) == {}
    assert reflection_site_tokens("no site here") == []
    assert reflection_site_tokens("asdict@cli._run_converge and eq@a.b") == [
        ("asdict", "cli._run_converge"),
        ("eq", "a.b"),
    ]


# ---------------------------------------------------------------- the findings acted on


def test_the_c_gate_record_carries_the_emissions_own_identity(tmp_path) -> None:
    """#94: `language`, `warrant` and `environment` were computed on the emission and read by nothing, so a
    gate result could not say which receipt it claimed to preserve or which toolchain it was declared
    against. They ride the record now, beside the toolchain the gate FOUND."""
    from Detective.emission import CrossLangEmission, run_c_gate

    emission = CrossLangEmission(
        "c", "long long f(long long x) { return x; }", "f", "cc 9.9 (declared)", "m.py::f@abc"
    )
    result = run_c_gate(emission, [(([1],), 1)], str(tmp_path))  # nothing portable: no compile needed
    assert result["language"] == "c"
    assert result["warrant"] == "m.py::f@abc"
    assert result["declared_environment"] == "cc 9.9 (declared)"
    assert "environment" in result  # the FOUND pin is a separate fact and is still recorded


def test_execution_binding_no_longer_carries_a_name_nothing_reads() -> None:
    import dataclasses

    from Detective.binding import ExecutionBinding

    assert "import_name" not in {f.name for f in dataclasses.fields(ExecutionBinding)}
