"""`detective doctor` — what is blocking correct USE of the tool (design: `docs/DOCTOR.md`).

Detective's guarantee is about measurement: it refuses rather than report a number measured against
the wrong file. Nothing in that guarantee reaches the OPERATOR, and the residual failure mode of the
whole project is a human or a model holding a partial model of it and acting on the gap.

THE FENCE, and it is load-bearing rather than a convention:

    Doctor diagnoses the OPERATOR and the ENVIRONMENT. It never speaks about the code.

It must never emit anything that reads as a correctness verdict — no "your code is fine", no
coverage claim, no completeness claim. The moment it does it has inherited exactly the
measurement/verdict conflation the project exists to kill, and it will be BELIEVED, because it is
the command a confused user runs. Consequences: advisory, writes nothing, never gates, cheap
(static reads and environment probes; it does not run the target's suite, profile mutants, or
import the target to find out).

THE HERBS (Resident Evil, and the mechanics are the design rather than a skin):

    GREEN   setup    present damage — the project or environment is malformed.  Works ALONE.
    RED     process  the operator is doing something wrong, or in the wrong order.  Completes green.
    YELLOW  taste    nothing is broken; something CAPS how much of Detective is reachable.

Yellow is the mapping that earns the scheme: taste findings heal nothing — an entangled function, an
overly broad discovery, a pure decision trapped in an impure shell — what they do is cap how much of
the tool is available. That is max health exactly.

WHY THE HERB NAMES STAY THE USER-FACING VOCABULARY (founder ruling 2026-09-09, and the reasoning is
the point — do not "clarify" these into `--setup/--process/--taste`):

    Nobody playing RE thinks through what each herb does. They remember that the combination is the
    goal and that green is the emergency. It becomes a heuristic, a spot in your head. The opacity
    REFUSES the pretence that whoever reaches for it — human or LLM — is doing so with conscious
    intent. And it is a check on exactly the wrong kind of confidence: a self-describing
    `--process` invites a model to fire it by pattern-match, whereas calling `--red` without the
    actual purposive context for why reads as an utterly ridiculous choice. The token that carries
    no meaning cannot lend false meaning to a guess.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess  # noqa: S404
import sys

# The ranking. GREEN outranks RED outranks YELLOW — a green fault invalidates red and yellow
# findings MEASURED THROUGH it (entanglement measured through a broken discovery is measuring the
# discovery), a red fault invalidates yellow findings that depend on a pin which does not exist, and
# yellow invalidates nothing because it only raises the ceiling.
HERBS = ("green", "red", "yellow")

# Which herb each command's own verdict belongs to (`docs/DOCTOR.md` §4). Every command knows its
# own herb, so the signpost trigger is DERIVED rather than a heuristic.
COMMAND_HERB: dict[str, str] = {
    "regime": "green",
    "converge": "red",
    "audit": "red",
    "diagnose": "red",
    "receipt": "red",
    "verify-rewrite": "red",
    "plan": "yellow",
    "survey": "yellow",
    "extract": "yellow",
    "decompose": "yellow",
    "parsimony": "yellow",
    "censor": "yellow",
}


def signpost_disposition(
    command_herb: str,
    green_finding: bool,
    red_finding: bool,
    yellow_finding: bool,
) -> str:
    """May this command emit its OWN verdict, or does a higher-ranked herb pre-empt it (pure —
    pinned).

    The one derivation behind three surfaces — doctor's combined report, the per-command signpost,
    and the ordered-remediation section. One derivation, three renderers, never a re-derived
    narrower proxy: that is the failure mode every repair in `docs/CORRECTNESS_REPAIRS_2026-09-08.md`
    turned out to be an instance of.

    THE RULE (§4): a command may emit its own verdict only when no HIGHER-ranked herb has a live
    finding. Otherwise it names that finding and offers the full mix.

      "emit"                  no higher-ranked finding and nothing lower worth naming — the command
                              speaks normally. A signpost here would be a line that always appears,
                              which is a line nobody reads.
      "emit_with_note"        the command may speak, but a LOWER-ranked finding is live and worth
                              naming. Distinct from `emit` because the difference is a visible line
                              of output, and distinct from the pre-emptions because the verdict is
                              still valid — it was not measured through the finding.
      "preempted_by_setup"    a GREEN finding outranks: the verdict would be measured through a
                              broken environment. Name the finding; do not emit.
      "preempted_by_process"  a RED finding outranks (yellow commands only): the taste half is being
                              run before the correctness half it presupposes.
      "unknown_herb"          a command outside `COMMAND_HERB` — NAMED, never admitted by
                              fall-through. A command whose herb nobody declared must not silently
                              acquire permission to speak; the same rule `admission_reason` applies
                              with `status_unknown`.

    A command is NEVER pre-empted by its own axis. A red command with a red finding IS the process
    statement — that is what it exists to say — so own-axis findings are not a higher rank. This is
    why the parameter is the command's herb and not "is there any finding".

    G+R is the general form of the converge spiral: converge (red) emitted "author these inputs"
    while a green fault (funcy absent from this interpreter) was live and pre-emptive. Neither axis
    alone catches it, which is the whole argument for the mix.
    """
    if command_herb not in HERBS:
        return "unknown_herb"
    if command_herb == "red" and green_finding:
        return "preempted_by_setup"
    if command_herb == "yellow":
        if green_finding:
            return "preempted_by_setup"
        if red_finding:
            return "preempted_by_process"
    lower = {
        "green": red_finding or yellow_finding,
        "red": yellow_finding,
        "yellow": False,
    }[command_herb]
    return "emit_with_note" if lower else "emit"


def setup_disposition(
    regime_conflict: str,
    pytest_importable: bool,
    missing_imports: tuple[str, ...],
    missing_but_elsewhere: tuple[str, ...],
    recorded_load_failure: bool,
    recorded_collection_failure: bool,
) -> str:
    """GREEN — present damage in the project or the environment (pure — pinned).

    Most-blocking first, and each code carries a DIFFERENT remedy, which is the whole reason they
    are not one `setup_broken` boolean:

      "regime_conflict"           the regime names a shadowed target or a conftest collision. Every
                                  verdict from this repo is untrustworthy — not "worse", WRONG in a
                                  way that reads as a finding. CONSUMED from `TestRegime.conflicts`,
                                  never re-derived (§5).
      "no_pytest"                 the interpreter that will run Detective cannot import pytest, so
                                  the live session cannot be opened at all. Detective already
                                  REFUSES here — correctly — and the refusal names the interpreter;
                                  what it cannot say is that this is a setup fault rather than a
                                  property of the repo.
      "deps_elsewhere"            THE MOTIVATING CASE, and the reason doctor exists. A module the
                                  target imports is absent from THIS interpreter and PRESENT under
                                  another one on this machine. The operator does not have an
                                  installation problem; they have a PROPAGATION problem, and every
                                  minute spent installing it again is spent moving away from the
                                  fix. Outranks `deps_missing` because naming the wrong one sends
                                  someone to reinstall a package they already have.
      "deps_missing"              absent here and not found under any interpreter we are allowed to
                                  look at. A genuine install — the ordinary case, ranked BELOW the
                                  surprising one on purpose.
      "stale_load_failure"        nothing is wrong with the environment now, but a recorded run
                                  failed to load the target. The remedy is to re-run, not to repair
                                  anything: this is doctor interrogating the PREMISE of a true
                                  statement, which is its whole job (§1).
      "stale_collection_failure"  same shape, for a test file that failed to collect.
      "clean"                     no setup damage found. NOT "your setup is correct" — the fence:
                                  doctor reports what it looked at and never certifies.

    THE STALE CODES ARE CONSUMED, NOT MEASURED, and that is only possible as of §MI: the certificate
    ledger now records `cut_reasons`, so `target_load_failed` / `collection_incomplete` are readable
    from disk. Before that a load failure was recorded as a bare `ungateable` standing with no
    reason, and doctor would have had to IMPORT THE TARGET to find out — which §1 forbids ("does not
    import the target to find out"). The fence and the capability arrived together by accident.

    `missing_but_elsewhere` is a SUBSET of `missing_imports` by construction, so a run with both
    reports `deps_elsewhere` and the render names every missing module either way (the S14a rule:
    whatever leads, the rest must still be named).
    """
    if regime_conflict:
        return "regime_conflict"
    if not pytest_importable:
        return "no_pytest"
    if missing_but_elsewhere:
        return "deps_elsewhere"
    if missing_imports:
        return "deps_missing"
    if recorded_load_failure:
        return "stale_load_failure"
    if recorded_collection_failure:
        return "stale_collection_failure"
    return "clean"


def process_disposition(drift: str, spiral: str, order: str) -> str:
    """RED — what the OPERATOR is doing wrong, or in the wrong order (pure — pinned).

    Red does nothing alone and completes green: knowing what you were TRYING to do turns "your venv
    lacks funcy" into "…and that is why your converge reported 0 kills and asked you for inputs;
    fix the import first, then re-run — do not author inputs."

    The three inputs are `ledger.environment_drift_disposition`, `ledger.spiral_disposition` and
    `ledger.order_disposition`, CONSUMED rather than re-derived. This only ranks them.

      "ground_moved"             the interpreter, the engine paths or the version changed between
                                 runs. FIRST, and not by taste: every other finding here is a
                                 comparison BETWEEN runs, and a comparison across changed ground is
                                 comparing different things. A "spiral" computed across an
                                 interpreter change is not a spiral — it is two measurements of two
                                 environments, and reporting it as a repeat would send the operator
                                 to stop doing the one thing that was actually varying.
      "spiral"                   the same command, twice or more, with nothing changing in between.
                                 The single highest-value process signal and the shape observed on
                                 conorheins: the operator followed the printed instruction and the
                                 instruction could not change the state.
      "order"                    the taste half is being run before the correctness half it
                                 presupposes — a seam proposed over an unpinned function cannot be
                                 proven behaviour-preserving.
      "repeat_no_change"         ONE repeat with nothing changed. Worth naming and not worth
                                 alarming about: two identical runs is how anyone checks a result.
                                 Kept distinct from `spiral` because the remedy differs — there is
                                 none here, it is just an observation.
      "clear"                    nothing in the history says the operator is stuck. NOT "you are
                                 using the tool correctly" — the fence: red reports observed
                                 process, never approves of it.

    `repeat_state_changed` and `progressed` never reach a finding, deliberately: an edit-then-rerun
    loop IS how the tool is used, and a process axis that flagged ordinary iteration would be noise
    on the one surface whose credibility is the product.
    """
    if drift in ("interpreter_changed", "engine_changed", "version_changed"):
        return "ground_moved"
    if spiral == "spiral":
        return "spiral"
    if order in ("taste_before_behaviour", "taste_without_measurement"):
        return "order"
    if spiral == "repeat_no_change":
        return "repeat_no_change"
    return "clear"


def mix_product(green_live: bool, red_live: bool, yellow_live: bool) -> str:
    """What the COMBINATION says that no single axis does (§3 — pure, pinned).

    This is the part of the herb scheme that is a mechanism rather than a metaphor. Red does
    nothing alone and completes green's axis; yellow raises a different axis entirely. So the mix
    is not three lists concatenated — it is three lists PLUS the statement of which findings must be
    re-derived after the repair, and in what order. That statement is the boost above the simple
    sum, and it is why the full mix is the default rather than something the operator must discover.

      "suppression"          G+R — "this process advice is void; that setup fault outranks it."
                             THE case doctor was built for: converge emitted "author these inputs"
                             (red) while funcy was missing from this interpreter (green), and the
                             inputs could never have helped. Neither axis alone catches it — green
                             does not know what you were trying to do, and red does not know why
                             the instruction could not work.
      "unreliability"        G+Y — the taste finding was MEASURED THROUGH a broken environment, so
                             it is measuring the environment. Re-derive after the fix; do not act.
      "ordering"             R+Y — you are about to do the taste half before the correctness half
                             it presupposes.
      "ordered_remediation"  all three — fix green, then re-derive red AND yellow, because both
                             were measured through the green fault.
      "none"                 fewer than two axes live. A product needs two things to multiply, and
                             printing a mix line over a single finding would be the line that
                             always appears.
    """
    live = (green_live, red_live, yellow_live)
    if all(live):
        return "ordered_remediation"
    if green_live and red_live:
        return "suppression"
    if green_live and yellow_live:
        return "unreliability"
    if red_live and yellow_live:
        return "ordering"
    return "none"


def command_setup_fault(
    regime_conflict: str,
    load_failed: bool,
    collection_incomplete: bool,
) -> str:
    """The GREEN fault a RUNNING command already holds the evidence for (pure — pinned).

    The signpost fires inside OTHER commands, so it cannot pay for green's full gathering: the
    cross-interpreter probe shells out once per candidate interpreter, and making every `converge`
    pay that would be a diagnostic tax on the healthy path. This is the free read — every input is
    something the command has already computed.

      "regime_conflict"        `TestRegime.conflicts`, which every command resolves before it runs
      "target_load_failed"     the run's OWN cut reason: the module would not import
      "collection_incomplete"  the run's OWN cut reason: a test file failed to collect
      "none"                   no setup fault this run can see for free. NOT "the setup is fine" —
                               the full read (`detective doctor`) probes things this cannot.

    DELIBERATELY NOT `setup_disposition` with empty probe arguments. That would return
    `stale_load_failure` for a load failure the CURRENT run just hit, and "a prior run recorded
    this, it may be stale" is the opposite of the truth here. Two questions that differ in tense
    are two decisions; collapsing them would put the wrong remedy under the right code, which is
    S13's defect one layer out.

    THE ORDER IS THE SAME AS `setup_disposition`'S and for the same reason: a regime conflict makes
    every verdict from the repo untrustworthy, so it outranks a fault in one target's measurement.
    """
    if regime_conflict:
        return "regime_conflict"
    if load_failed:
        return "target_load_failed"
    if collection_incomplete:
        return "collection_incomplete"
    return "none"


def taste_disposition(
    scanned: int,
    extractable_core: int,
    impure_body: int,
    trapped_by_imports: int,
    unresolved_param: int,
) -> str:
    """YELLOW — what CAPS how much of Detective this code lets you reach (pure — pinned).

    Yellow is the mapping that earns the herb scheme, and the reason its codes must not read like
    green's: none of this is damage. An entangled function is not broken, an inexpressible parameter
    is not a bug, a pure decision trapped behind a heavy import runs perfectly. What they do is put
    a CEILING on how much of the tool is available — max health, exactly.

    The ranking is `survey_disposition`'s own, CONSUMED rather than restated (§5): it already orders
    these most-blocking first and says why each outranks the next. Restating the order here would
    be a second reader of the same facts, which is the drift every repair in
    `docs/CORRECTNESS_REPAIRS_2026-09-08.md` turned out to be an instance of.

      "extractable_core"     a parameter has no literal form, so the pure sub-decision it wraps is
                             unreachable by ANY `--input`. The highest ceiling and the hardest to
                             raise — the extraction is the parameter itself.
      "impure_body"          params are expressible; the body is entangled with world effects. The
                             decision can be split from the I/O.
      "trapped_by_imports"   pure and expressible, but the MODULE's top-level imports are the heavy
                             stack, so converge cannot load it cheaply.
      "unresolved_param"     the question is OPEN — a usage no supported inference resolves. Ranked
                             below every PROVEN block because it is not a claim that anything is in
                             the way, and above `clear` because silence would lose it (R4).
      "clear"                nothing found is capping what converge can reach here. NOT "this code
                             is good" — the fence: yellow reports a ceiling, never a quality.
      "nothing_to_read"      no functions were scanned at all. Distinct from `clear` because "we
                             looked and found nothing in the way" and "there was nothing to look
                             at" are different facts, and `plan` already names this one
                             (`NOTHING_TO_READ`) rather than reporting a clean read of an empty set.

    NOT the same question as "did doctor read yellow at all". A caller that declined to scan — the
    directory-scope degradation (§7.4) — reports `not read` with its reason, which is the caller's
    fact and not derivable from these counts. Collapsing the two would let an unread axis render as
    a clean one, which is the single failure this whole surface exists to prevent.
    """
    if scanned <= 0:
        return "nothing_to_read"
    if extractable_core > 0:
        return "extractable_core"
    if impure_body > 0:
        return "impure_body"
    if trapped_by_imports > 0:
        return "trapped_by_imports"
    if unresolved_param > 0:
        return "unresolved_param"
    return "clear"


# ─────────────────────────────────────────────────────────────────────────────
# The gathering layer (impure — hand-tested for durability, never converge-pinned).
#
# EVERY function here is advisory and MUST NOT raise: doctor is the command a confused user runs,
# and a diagnostic that dies on the way to explaining a failure is worse than no diagnostic. Each
# probe degrades to "I could not look", which the render reports as such — an absence DISCLOSED,
# never an absence silently read as "nothing wrong". That distinction is the whole project.
# ─────────────────────────────────────────────────────────────────────────────

# How far the cross-interpreter probe may look (§7.3). NOT a filesystem sweep: venvs at or beside
# the project root, and the interpreters on PATH. A machine-wide hunt would be slow, would surface
# interpreters the operator has no relationship with, and would turn a bounded inference into a
# guess.
_VENV_DIRS = (".venv", "venv", ".venv312", ".venv311", "env", ".env")
_PATH_PYTHONS = ("python3", "python")
_PROBE_TIMEOUT_S = 5.0


def target_imports(path: str) -> tuple[str, ...]:
    """The TOP-LEVEL package names a target file imports, read statically (never raises).

    AST, not import: §1 forbids importing the target to find out, and this is the probe that makes
    the fence affordable. Only the first dotted segment, because `importlib.util.find_spec` on a
    DOTTED name imports the parent packages to locate the child — which would execute code and
    break the fence in the one place it matters most.

    Relative imports are skipped (the target's own package, not a dependency) and so is anything in
    `sys.stdlib_module_names`: a stdlib module is never the propagation case, and reporting one
    would be noise on a surface whose credibility is the product.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, ValueError):
        return ()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return tuple(sorted(n for n in names if n and n not in sys.stdlib_module_names))


def missing_here(names: tuple[str, ...]) -> tuple[str, ...]:
    """Which of ``names`` THIS interpreter cannot find (never raises).

    `find_spec` locates without executing, and every call is guarded: a package whose finder itself
    raises is reported MISSING rather than present, because "we could not establish that it is
    importable" and "it is importable" are different facts, and only the conservative one is safe on
    a surface that tells people what to install.
    """
    missing: list[str] = []
    for name in names:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError, AttributeError, TypeError):
            missing.append(name)
    return tuple(missing)


def candidate_interpreters(root: str) -> tuple[str, ...]:
    """The interpreters the cross-interpreter probe may ask, bounded per §7.3.

    Excludes the RUNNING interpreter: it is the one missing the package, so asking it again is the
    tautology the operator is already stuck inside.
    """
    found: list[str] = []
    here = os.path.realpath(sys.executable)
    for parent in (root, os.path.dirname(os.path.abspath(root))):
        for vd in _VENV_DIRS:
            for exe in (("bin", "python3"), ("bin", "python"), ("Scripts", "python.exe")):
                cand = os.path.join(parent, vd, *exe)
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    found.append(cand)
    for name in _PATH_PYTHONS:
        which = shutil.which(name)
        if which:
            found.append(which)
    out: list[str] = []
    seen = {here}
    for cand in found:
        real = os.path.realpath(cand)
        if real not in seen:
            seen.add(real)
            out.append(cand)
    return tuple(out)


def found_elsewhere(names: tuple[str, ...], interpreters: tuple[str, ...]) -> dict[str, str]:
    """Map each of ``names`` that EXISTS under some other interpreter to that interpreter's path.

    THE INFERENCE THE OPERATOR CANNOT BE EXPECTED TO MAKE, and the reason doctor exists. The CLI
    says `ModuleNotFoundError: No module named 'funcy'` and every word is true; the premise a reader
    infers from it — *you do not have funcy* — is false. Naming both paths turns "install it again"
    into "your install went somewhere else", which is the difference between the fix and an hour
    spent moving away from it.

    One subprocess per candidate, asking about every name at once, with a hard timeout. Never
    raises: an interpreter that hangs, dies, or answers rubbish is one that told us nothing.
    """
    if not names or not interpreters:
        return {}
    probe = (
        "import importlib.util as u, sys\n"
        "for n in sys.argv[1:]:\n"
        "    try:\n"
        "        if u.find_spec(n) is not None:\n"
        "            print(n)\n"
        "    except Exception:\n"
        "        pass\n"
    )
    out: dict[str, str] = {}
    for interp in interpreters:
        try:
            # S603: the argv is this module's own literal probe plus names read from the target's
            # AST — never shell-interpreted, and the executable comes from the bounded candidate set
            run = subprocess.run(  # noqa: S603
                [interp, "-c", probe, *names],
                capture_output=True,
                text=True,
                timeout=_PROBE_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        for line in run.stdout.splitlines():
            name = line.strip()
            if name in names and name not in out:
                out[name] = interp
    return out


def recorded_cut_reasons(root: str, func_key: str = "", write_dir: str = "") -> tuple[str, ...]:
    """Cut reasons a PRIOR run recorded, read from the certificate ledger (never raises).

    Consumed rather than measured, which is only possible as of §MI: the ledger now records
    `cut_reasons` per certificate, so `target_load_failed` / `collection_incomplete` are readable
    from disk WITHOUT importing the target — the thing §1 forbids. Before that repair an invalid
    measurement was stored as a bare `ungateable` standing with no reason, and this probe could not
    have existed inside the fence. The capability and the fence arrived together.

    With no ``func_key`` the whole ledger is unioned: "your recent runs recorded these" is the
    honest repo-scoped answer. A record written before the field existed carries no `cut_reasons`
    key and contributes nothing — absent is not empty (§MI), and this reader must not turn one into
    the other.
    """
    from .certificates import CERTIFICATES_FILENAME, DEFAULT_WRITE_DIR

    target_dir = write_dir or DEFAULT_WRITE_DIR
    base = target_dir if os.path.isabs(target_dir) else os.path.join(os.path.abspath(root), target_dir)
    try:
        with open(os.path.join(base, CERTIFICATES_FILENAME), encoding="utf-8") as fh:
            entries = json.load(fh)
    except (OSError, ValueError):
        return ()
    if not isinstance(entries, dict):
        return ()
    rows = [entries.get(func_key)] if func_key else list(entries.values())
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for reason in row.get("cut_reasons", ()) or ():
            if isinstance(reason, str) and reason not in out:
                out.append(reason)
    return tuple(out)


def red_facts(root: str, herb_of: dict | None = None) -> dict:
    """Read the ledger and answer RED's four questions about the operator (never raises).

    Reports on the most recent NON-DOCTOR invocation, because doctor is the command you just ran
    and "you ran doctor twice" is not the finding anyone came for. If nothing else is on record the
    answer is `available` with no subject, which is honest — history exists and says nothing yet.

    Returns the four CODES, consumed from `ledger`'s pinned decisions rather than re-derived here,
    plus the row they describe so the render can name the verb and target. `available` is separate
    from every code: an unreadable or missing ledger means process findings are UNAVAILABLE, which
    is not the same as no finding, and rendering the first as the second is the one thing this
    surface must never do.
    """
    from . import ledger as _L

    out = {
        "available": _L.ledger_available(root),
        "subject": None,
        "spiral": "no_prior",
        "drift": "no_prior",
        "order": "ok",
        "outcome": "unobserved",
    }
    if not out["available"]:
        return out
    rows = [r for r in _L.read_recent(root, limit=200) if isinstance(r, dict)]
    subjects = [r for r in rows if r.get("verb") != "doctor"]
    if not subjects:
        return out
    latest = subjects[-1]
    out["subject"] = latest
    verb, target = latest.get("verb", ""), latest.get("target")
    # The comparison set: the SAME verb on the SAME target, older than the subject. A different
    # target is a different question, and mixing them would manufacture repeats out of ordinary
    # work across a codebase.
    prior = [r for r in subjects[:-1] if r.get("verb") == verb and r.get("target") == target]
    same_args = bool(prior) and prior[-1].get("args") == latest.get("args")
    same_state = bool(prior) and prior[-1].get("state") == latest.get("state")
    identical = 0
    for row in reversed(prior):
        if row.get("args") == latest.get("args") and row.get("state") == latest.get("state"):
            identical += 1
        else:
            break
    out["spiral"] = _L.spiral_disposition(bool(prior), same_args, same_state, identical)

    prev_env = (prior[-1].get("env") or {}) if prior else {}
    env = latest.get("env") or {}
    out["drift"] = _L.environment_drift_disposition(
        bool(prior),
        prev_env.get("interpreter") == env.get("interpreter"),
        (prev_env.get("detective"), prev_env.get("wesker")) == (env.get("detective"), env.get("wesker")),
        prev_env.get("version") == env.get("version"),
    )

    herb = (herb_of or COMMAND_HERB).get(verb, "")
    func_key = str(target) if target and "::" in str(target) else ""
    ever_pinned = _target_ever_pinned(root, func_key)
    measured = any(r.get("target") == target and r.get("verb") in ("converge", "audit") for r in subjects)
    out["order"] = _L.order_disposition(herb, ever_pinned, measured)

    obs = latest.get("outcome") or []
    mine = [o for o in obs if len(o) >= 2 and o[1] == verb]
    others = [o for o in obs if len(o) >= 2 and o[1] != verb]
    codes = {o[2] for o in mine if len(o) >= 3}
    out["outcome"] = _L.outcome_disposition(len(mine), len(others), len(codes) <= 1)
    out["outcome_code"] = next(iter(codes), "") if len(codes) == 1 else ""
    return out


def _target_ever_pinned(root: str, func_key: str) -> bool:
    """Whether the certificate ledger records a COMPLETE standing for this target (never raises).

    Consumed from the certificate the behaviour layer already writes, rather than asking the ledger
    whether a converge "looked successful" — a converge that ran is not a converge that pinned, and
    `order_disposition`'s question is about the CONTRACT existing, not about the command having
    been issued.
    """
    if not func_key:
        return False
    try:
        from .certificates import load_certificate

        cert = load_certificate(root, func_key, "")
        return bool(cert) and cert.get("standing") == "complete"
    # BLE001: an unreadable certificate is "not pinned", never a raised diagnostic
    except Exception:  # noqa: BLE001
        return False


def pytest_importable() -> bool:
    """Whether the interpreter that will run Detective can import pytest (never raises).

    Detective already REFUSES without it, correctly, and names the interpreter. What that refusal
    cannot say — because it is not a claim about the measurement — is that this is a SETUP fault
    rather than a property of the repository, which is the inference a greenfield user gets wrong.
    """
    try:
        return importlib.util.find_spec("pytest") is not None
    except (ImportError, ValueError, AttributeError, TypeError):
        return False
