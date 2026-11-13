# Proposal

## Why

Wesker and Detective instantiate the knowability paper: a survivor of an output mutant is read exactly
(output coverage), and the tools' certificates are honest about what they establish. But the tools run a
far wider regime than output mutation — ten program-text categories and the two-sign codomain family —
and for a survivor of that regime they can say only `killable`, `candidate-equivalent — UNPROVEN`, or a
fixture/structural caveat. Three different situations with three different remedies share the UNPROVEN
sign today: a branch no input can reach, a distinction the code makes and then erases, and a genuine
rewording. All three invite a `flag`. That is a collision by COMMUNICATING_DETERMINISM's own rule, and it
is also a waste: most of what converge asks a person for per run (`--input`) is not intent at all
(NEGATIVE_SPECIFICATION Prop 4.3) and could be settled by structure or by the call-site population.

`docs/theory/knowability_ii/KNOWABILITY_II.md` says what the wider regime can know, and this change
builds it.

## What Changes

- **Wesker** gains (W1) the missing BOUNDARY guards the paper's theorem shows are uncertified (`!=` for
  `<`/`>`; one-sided guards for `==`/`!=` on orderable operands) with a policy-id bump; (W2) a per-test
  site trace — reached / infected / propagated — as optional annotation on every survivor record; (W3) a
  reach formula and an infect formula per mutant in the literal language; (W4) surprise counts with a
  measured propagation base; (W5) the report schema for all of the above, defaulting absent.
- **Detective** gains (D1) a standard-library exact solver over premises and formulas with verdicts
  ENTAILED / REFUTED / UNDETERMINED / INCONSISTENT and the minimal deciding premise set; (D2) a premise
  ledger (`.detective/premises.json`) with origins, statuses, scopes and an S-version, into which `flag`,
  `--fence`, `censor` and `default` write; (D3) the typed survivor state — the alphabet of KNOWABILITY_II
  §5 — as a pure pinned decision with an injectivity intent test; (D4) solver-directed witness synthesis
  and the mechanical collapse of DOF⁰; (D5) κ by re-entailment with brackets and S-version, the ordered
  teacher queue, the stopping rule, and `d` measured on the call-graph quotient; (D6) corpus censors as
  proposed premises behind the existing admissibility guard; (D7) surprise rendering and the
  absent-expected-kill rule; (D8) the negative twins for state, exceptions, per-site returns and streams;
  (D9) the five-number report; (D10) the surface: `detective ask`, the max-κ imperative in `DO THIS`,
  vocabulary, COMMUNICATING_DETERMINISM's new collisions.
- **Both**: validation of the six predictions of KNOWABILITY_II §11 (V1–V6), pointers, CHANGELOG, paired
  release notes.

## Capabilities

### New Capabilities

Site trace (Wesker); constraint emission (Wesker); exact premise solver (Detective); premise ledger
(Detective); survivor state alphabet (Detective); κ/surprise ordering (Detective); five-number report
(Detective); `detective ask` and `detective premises` verbs (Detective).

### Modified Capabilities

BOUNDARY operator basis (Wesker; universe change, policy id bump). `residual_disposition` and
`candidate_equivalent_caveat` consume the new state (Detective; old codes retained). `censor` output
gains κ brackets (Detective). `converge`/`audit` terse and `--json` gain optional fields (Detective).

`skip_specs: true`: the theory document and ARCHITECTURE are the contract oracle; each task names the
section it implements.

## Impact

Both repositories; the planning home is Detective. Policy id moves once (W1) and consumers that key on it
(Detective receipts, certificates) treat the old universe's claims as the old universe's — that is what
the id is for. Nothing changes for a run with the new features off (V5). No new dependency. The MCP
surface stays parked.
