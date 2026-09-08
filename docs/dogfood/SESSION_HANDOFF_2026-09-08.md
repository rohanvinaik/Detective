# Session handoff — 2026-09-08

Grounding for whoever picks this up (including a post-compact me). **Read this, then
`docs/CORRECTNESS_REPAIRS_2026-09-08.md`. Ground every claim against current source before acting
— that document is now largely fix-GUIDING and therefore anti-correlated with truth where a row
says RESOLVED.**

## What this session was

An A/B stress-test of the uncommitted 2026-09-07 closure wave, run as a greenfield user over four
foreign repos (`michaelhodel/arc-dsl`, `takmakov/GofL`, `conorheins/collective_motion_actinf`,
`parama/pabkit`), all 15 CLI verbs, both engine arms — followed by repairs of everything it found.

Harness (still on disk, scratchpad): `ab/run.sh` (full-capture runner), `ab/engines/*_HEAD`
(git worktrees at the pre-wave commits), `ab/repos_{with,without}/*` (pristine clones, separate per
arm because converge WRITES), `ab/.venv-det` (jax/funcy/matplotlib/torch deliberately ABSENT — that
absence is the conorheins repro, do not install into it), `ab/AB_LEDGER_2026-09-08.md`,
`ab/r0_probe.py`, `ab/migrate_noqa.py`.

**Two-knob proof from the target repo's cwd, every time.** `python -c` puts cwd at `sys.path[0]`,
so a proof run from inside the Detective repo reports the working tree for BOTH arms and the whole
A/B silently becomes vacuous. This nearly happened.

## Landed (13 commits, Detective) + Wesker c10e136

R0 (Finding B: fixed not suppressed, probed independently) · R1 (`target_load_failed` cut reason) ·
R2 (derived Why; bounded-search wording) · R3 (shared block route consulted unconditionally; the
dependency named) · R4 (`unresolved_param` — GofL recovered) · R5/R5b (recorded) · S1 S2 S6 S7 S8
S11 S12 S13 S16 S17.

## Still open — all founder calls, none blocked on work

| | |
|---|---|
| **S9** | third-party warning spam — struck as calibration, not a defect |
| **S10** | cache-consistency flake. 0/10 isolated, 0/4 recent full runs, 1 in the first three. Likely the post-purge WARM read misses and recomputes, re-exposing it to count noise its docstring claims immunity from — the CLAIM is wrong, not the cache. Next step: assert the warm read was a cache HIT. |
| **S14** | which reason's remedy leads when several cut reasons are live |
| **S15** | four in-repo decisions refuse with `mutant_not_entered` (`measurement_cut_reasons`, `line_gap_why`, `converge_next_action`, `repair_measurement_route`) — the running Detective calls them while profiling itself. **Founder ruled: stay on hard pins**, no `DetectiveUUT` migration. |
| **U1** | pabkit's open call — should an un-evaluable universe REFUSE rather than fold into a 0-kill Incomplete. Much closer now that S13 made the reasons nameable. |
| **doctor** | `docs/DOCTOR.md` designed, NOT built. Needs the invocation ledger's persistence shell (`docs/INVOCATION_LEDGER.md`) — the process-scoped channel exists and is wired for converge; `.detective/ledger.jsonl`, digests and pruning are not written. `_audit_action` is deliberately NOT wired: its ladder has no single named code, and inventing one recreates the drift R3 removed. |

## Three habits this session earned the hard way

1. **Trace before repairing.** Twice the wave had already fixed the thing the design doc said to
   fix (R2b; R3's verify-rewrite half). A fix-guiding note is anti-correlated with current truth.
2. **A test's name and its assertion must agree.** Three instances found —
   `test_gofl_update_cell_step_infers_ndarray` asserting `== ""`,
   `test_unmeasured_mutant_closure_intent`'s title distinguishing what its body merged, and
   `test_a_tuple_subscript_does_not_establish_an_array_type` asserting silence stronger than its
   name. Each made the pinned thing invisible to anyone reading the test list. A standing check
   that names match assertions would have caught all three.
3. **Converge before wiring, measured.** `line_gap_why` was inserted AND wired in one step; its
   covering set inflated and converge ran past 600s with an empty progress file. Unwired, the same
   target finished in seconds.

## Gate discipline, corrected this session

- `pytest` **bare** — `addopts` already carries `-q`; a second makes it `-qq` and the summary line
  vanishes. This ate a count twice, once at my prompt and once in CI (S16).
- `ruff format --check .` **whole-tree**, not `Detective tests` — CI's scope is wider and the
  narrower gate let an unformatted file through (S17). Now corrected in CLAUDE.md.
- noqa house form is now: reason on its own line above as `# CODE: <reason>`, bare `# noqa: CODE`
  on the code line. The old recorded cause (a comma) was wrong; it is the trailing prose (S12).
- `cat` is a shell function wrapping `bat`; it falls through to real `cat` on any flag.
